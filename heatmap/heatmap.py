# -*- coding: utf-8 -*-
"""
Created on Mon Jun  9 10:59:15 2023

@author: vbja
"""

from shiny import App, ui
from shinywidgets import output_widget, render_widget
import plotly.graph_objs as go
import numpy as np
from PIL import Image
import os
from dataclasses import dataclass
from scipy.interpolate import interp1d


def read_poly(pstr):
    try:
        order = int(pstr.split("x^")[1].split()[0])
    except IndexError:
        order = 1
    coeffs = np.zeros(order + 1)
    if pstr[0] == "-":
        sign = pstr[0]
        pstr = pstr[1:]
    else:
        sign = ""

    for coeff in pstr.split():
        if coeff == "+":
            sign = "+"
            continue
        elif coeff == "-":
            sign = "-"
            continue

        coeffsplit = coeff.split("x")
        coeff = float(coeffsplit[0])
        if len(coeffsplit) == 1:
            coeffdeg = 0
        else:
            coeffdeg = coeffsplit[1]
            if "^" in coeffdeg:
                coeffdeg = int(coeffdeg.replace("^", ""))
            else:
                coeffdeg = 1

            if sign == "-":
                coeff = -coeff

        coeffs[order - coeffdeg] = coeff

    polynomial = np.poly1d(coeffs)
    return polynomial


def read_f_di(di_str, i):
    params = di_str.split()
    d_0 = float(params[0])
    alpha = np.deg2rad(float(params[1].replace("(sin(", "").rstrip(")")))
    L = float(params[3].lstrip("("))
    gamma = np.deg2rad(float(params[5].replace("cos(", "").rstrip(")")))
    x_0 = float(params[11].replace("sqrt((", ""))
    s = float(params[13].replace("i)^2", ""))

    return d_0 * (np.sin(alpha) - (L - np.cos(gamma) * (L * np.cos(gamma) + x_0 + s * i)) / np.sqrt(
        (x_0 + s * i) ** 2 + (L * np.sin(gamma)) ** 2))


@dataclass()
class LIXSData:
    filename: str
    z: float
    width: float
    height: float
    prange: list[float]
    intensity: list[float]
    wavelength: list[float]


coefficients = np.array([-2.74125986e-15, 1.35973387e-11, -2.36111393e-08, 1.71252695e-05,
                         3.19777372e-03, 3.99709714e+00])

app_ui = ui.page_fluid(
    ui.head_content(
        ui.tags.script("""
                            var dimension = [0, 0];
                            $(document).on("shiny:connected", function(e) {
                                dimension[0] = window.innerWidth;
                                dimension[1] = window.innerHeight;
                                Shiny.onInputChange("dimension", dimension);
                            });
                            $(window).resize(function(e) {
                                dimension[0] = window.innerWidth;
                                dimension[1] = window.innerHeight;
                                Shiny.onInputChange("dimension", dimension);
                            });
                        """),
    ),
    ui.include_css("./hack.css"),
    ui.input_dark_mode(id="mode"),
    ui.div(
        ui.input_action_button("home", "home", onclick="location.href='https://shinychem.duckdns.org';"),
        style="display:inline-block; position:relative; left:calc(50%);",
    ),
    ui.layout_sidebar(
        ui.sidebar(
            ui.input_select("material", "Choose material:",
                            {
                                "LiF": "LiF", "Al": "Al", "Ni": "Ni"
                            },
                            ),
            ui.input_file("files", "Alternatively, choose files:", multiple=True, accept=".tif"),

            # ui.input_checkbox("uselog", "Use log scale", False),
            ui.input_checkbox("usewl", "Show wavelength instead of pixel number", True),
            ui.input_select("colorscale", "Choose colorscale:",
                            {
                                "viridis": "viridis", "gray": "gray", "inferno": "inferno"
                            },
                            ),
            width="600px",
        ),
        ui.h1("LIXS Plasma Expansion Heatmap"),
        ui.input_text("pstr", "Calibration function for wavelength calibration",
                      value="5.0463e-10x^3 - 1.2594e-06x^2 + 8.8623e-03x + 3.4787e+00", width="100%"),
        output_widget("plot_heatmap"),
    ),
    title="LIXS Heatmap"
)

take_average = True


def server(input, output, session):
    @render_widget
    def plot_heatmap():
        THICKNESS = 0
        if not input.files():
            # List of relevant files
            material = input.material()
            filenames = os.listdir(material)
            filenames = [filename for filename in filenames if filename.endswith('.tif')]

            z_list = [float(x.split("_")[1]) + THICKNESS for x in filenames]

        else:
            print(input.files())
            filenames = [x['datapath'] for x in input.files()]
            z_list = [float(x['name'].split("_")[1]) for x in input.files()]
            material = "??"

        if material == "Ni":
            THICKNESS = 5

        fig = go.Figure()
        z_list, filenames = zip(*sorted(zip(z_list, filenames)))

        imgdata = []

        # Iterate through each filename
        for filename, z in zip(filenames, z_list):
            if z > 3:
                continue
            # Load the image and get its dimensions
            image = Image.open(os.path.join(material, filename))
            width, height = image.size
            data = np.array(image)

            # Sum the intensities of each column
            intensity = np.sum(data, axis=0)
            prange = np.array(range(len(intensity)))  # Pixel Number

            if "sin" in input.pstr():
                wavelength = read_f_di(input.pstr(), prange)
            else:
                polynomial = read_poly(input.pstr())

                wavelength = polynomial(prange)

            # Apply compressed sensing if 'use_cs' is True
            imgdata.append(LIXSData(filename, z, width, height, prange, intensity, wavelength))

        imgdata = sorted(imgdata, key=lambda x: x.z, reverse=True)
        # Create an empty 2D array to store intensity values
        intensity_dict = {}

        # Populate the intensity dictionary with intensity values
        if take_average:
            # Populate the intensity dictionary with intensity values
            for img in imgdata:
                if img.z not in intensity_dict:
                    intensity_dict[img.z] = [img.intensity]
                else:
                    intensity_dict[img.z].append(img.intensity)

            # Calculate the average intensity for each "z" value
            for z, intensities in intensity_dict.items():
                intensity_dict[z] = np.mean(intensities, axis=0)
        else:
            for img in imgdata:
                if img.z not in intensity_dict:
                    intensity_dict[img.z] = np.zeros(len(img.prange))
                intensity_dict[img.z] += img.intensity  # add up

        # Define prange
        prange = imgdata[0].prange

        # Get the unique z values
        z_values = list(intensity_dict.keys())

        cblabel = f"Intensity [16bit]"

        # Create a heatmap
        intensity_matrix = np.vstack([intensity_dict[z] for z in z_values])
        wavelength_matrix = np.vstack([img.wavelength for img in imgdata])

        # Create a common wavelength grid
        common_wavelength_grid = np.linspace(min(wavelength_matrix[0]), max(wavelength_matrix[0]), 1000)

        # Interpolate intensities onto the common wavelength grid
        interpolated_intensities = np.array([interp1d(wavelength_matrix[i], intensity_matrix[i], kind='linear',
                                                      fill_value="extrapolate")(common_wavelength_grid) for i in
                                             range(len(z_values))])

        if input.usewl():
            trace = go.Heatmap(
                z=interpolated_intensities,
                x=common_wavelength_grid,
                y=z_values,
                colorscale=input.colorscale(),
                colorbar=dict(title=cblabel),
                zmin=np.min(interpolated_intensities),
                zmax=np.max(interpolated_intensities),
            )
            fig.add_trace(trace)
            fig.update_xaxes(title_text="Wavelength [nm]")
        else:
            trace = go.Heatmap(
                z=intensity_matrix,
                x=prange,
                y=z_values,
                colorscale=input.colorscale(),
                colorbar=dict(title=cblabel),
                zmin=np.min(intensity_matrix),
                zmax=np.max(intensity_matrix),
            )
            fig.add_trace(trace)
            fig.update_xaxes(title_text="Pixel Number [-]", range=[0, 2048])

        fig.update_yaxes(title_text="Target Defocus [mm]", tickvals=np.arange(
            max(z_values), min(z_values) - 1, -1), tickfont_size=18, title_font_size=20)
        fig.update_xaxes(tickfont_size=18, title_font_size=20)
        fig.update_layout(height=input.dimension()[1] - 275, width=input.dimension()[1] - 175)
        return fig
        # fig.savefig(os.path.join(r"G:\Limit\vbja\LIXS_heatmaps", f"heatmap_{material.lower()}_gray.png"), bbox_inches='tight')

        # csv_filename = os.path.join(basedir, f"intensity_matrix_{material.lower()}.csv")
        # # Combine z values and intensity matrix
        # export_data = np.column_stack((z_values, intensity_matrix))
        # header = ["Z [mm]"] + [str(i) for i in range(1, len(prange) + 1)]

        # # Save to CSV with headers
        # np.savetxt(csv_filename, export_data, delimiter=';', header=';'.join(header), comments='')


app = App(app_ui, server)
