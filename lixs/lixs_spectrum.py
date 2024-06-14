#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri May  3 20:23:39 2024

@author: vonballmoos
"""
import plotly.graph_objs as go
from plotly.subplots import make_subplots
from PIL import Image
import numpy as np
from shinywidgets import output_widget, render_widget
from shiny import App, ui, render, reactive
from shiny.types import ImgData

import pandas as pd
from scipy.signal import find_peaks, peak_prominences

h_planck = 4.1356676969e-15
c = 299792458


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


def unique_peaks(peaks, peak_heights, i_reference, distance, relative_height_threshold, show_common):
    unique_peaks = []
    unique_heights = []

    allpeaks = [x for i, x in enumerate(peaks) if i != i_reference]
    allheights = [y for i, y in enumerate(peak_heights) if i != i_reference]

    for filepeaks, filepeak_heights in zip(allpeaks, allheights):
        for peak, height in zip(filepeaks, filepeak_heights):
            is_unique = True
            for p, h in zip(peaks[i_reference], peak_heights[i_reference]):
                if abs(peak - p) <= distance and abs(height - h) <= max(h, height) * relative_height_threshold:
                    is_unique = False
                    break
            if not show_common:
                if is_unique:
                    unique_peaks.append(peak)
                    unique_heights.append(height)
            else:
                if not is_unique:
                    unique_peaks.append(peak)
                    unique_heights.append(height)

    return unique_peaks, unique_heights


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
            ui.input_file("filenames", "Select .tif file(s)", multiple="True", accept=".tif"),
            ui.input_checkbox("uselog", "Use Log Scale", False),
            # ui.input_checkbox("usewl", "Choose x-axis", True),
            ui.input_select("xaxis", "Choose x-axis:",
                            {
                                "px": "Pixels", "wl": "Wavelength", "ev": "Energy"
                            },
                            selected="wl"
                            ),
            ui.download_button("save_spectrum", "Save spectrum data"),

            ui.card(
                ui.input_checkbox("nist", "Show NIST lines", False),
                ui.input_text("element", "Chemical Symbol", value="Al", width="60px"),
            ),
            ui.card(
                ui.input_checkbox("pc", "Compare peaks", False),
                ui.input_select("reference", "Select reference spectrum", []),
                ui.input_slider("prominence_factor", "Prominence factor of peak detection", 0.1, 99.9, 1, step=0.1,
                                post="%"),
                ui.input_slider("height_threshold", "Relative height threshold for peak difference", 1, 100, 100,
                                step=1, post="%"),
                ui.input_slider("distance", "Pixel offset tolerance", 0, 15, 5, step=1, post="pixels"),
                ui.input_checkbox("common", "Show common instead of unique peaks", False),

            ),
            ui.card(
                ui.input_select("select_image", "Select .tif of LIXS panel", []),
                ui.input_checkbox("normalize", "Normalize image intensities", True),
                ui.input_checkbox("panel_sqrt", "Take sqare root of image intensities", False),
            ),
            ui.output_table("clickedPoints"),
            ui.div(
                ui.download_button("save", "Save clicked points to .csv", width="45%"),
                ui.input_action_button("modal", "Search for elements of peaks", width="45%"),
                style="display: flex; justify-content: space-between;"
            ),
            width="500px",
        ),
        ui.div(
            ui.h1("LIXS spectrum"),
            ui.input_text("polyfun", "Calibration function for wavelength calibration",
                          value="5.0463e-10x^3 - 1.2594e-06x^2 + 8.8623e-03x + 3.4787e+00", width="100%"),
            output_widget("plot_LIXS"),
            ui.div(
                ui.output_image("image", height="100px"),
                style="margin-top: 10px;"  # Ensure space between plot and image
            ),
            style="display: flex; flex-direction: column;"
        )
    ),
    title="LIXS Spectrum",
)


def server(input, output, session):
    @render_widget
    def plot_LIXS():

        # Read NIST lines
        df_nist = pd.read_pickle('nist_lines.pkl')

        if not input.filenames():
            raise NameError("Please select a valid .tif file")
            return

        maxintensity = 0

        fig = go.FigureWidget(make_subplots(specs=[[{"secondary_y": True}]]))
        # fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.05)

        mode = input.xaxis()

        def get_df_columns(mode):
            if mode == "ev":
                return ['Energy [eV]', 'Intensity [64 bit]', 'Filename']
            else:
                return ['Wavelength [nm]', 'Intensity [64 bit]', 'Filename']

        wavelength_list = []

        # Initialize an empty DataFrame for wavelengths
        wavelength_df = reactive.Value(pd.DataFrame(wavelength_list, columns=get_df_columns(input.xaxis())))

        @render.table
        def clickedPoints():
            return wavelength_df.get()

        all_intensity = []
        filenames = []

        if input.pc():
            allpeaks = []
            allpeakheights = []

        for filedata in input.filenames():
            file = filedata['datapath']
            filename = filedata['name']
            filenames.append(filename)

            # Load the image and get its dimensions
            image = Image.open(file)
            width, height = image.size
            data = np.array(image)

            # Take the mean of the intensities of each column
            intensity = np.mean(data, axis=0)
            all_intensity.append(intensity)

            prange = np.array(range(len(intensity)))  # Pixel Number

            maxintensity = max(maxintensity, max(intensity))
            if input.pc():
                prominence_threshold = max(intensity) * input.prominence_factor() / 100
                peaks, _ = find_peaks(intensity, prominence=prominence_threshold)
                peak_heights = intensity[peaks]

                allpeaks.append(peaks)
                allpeakheights.append(peak_heights)

            pstr = input.polyfun()

            if "sin" in pstr:
                wavelength = read_f_di(pstr, prange)
            else:
                polynomial = read_poly(pstr)
                # Apply calibration to map pixel positions to wavelengths
                wavelength = polynomial(prange)

            if mode == "wl":
                fig.add_trace(go.Scatter(x=wavelength, y=intensity, mode='lines', name=filename), secondary_y=False)

            elif mode == "ev":
                energy = h_planck * c / (wavelength * 1e-9)
                fig.add_trace(go.Scatter(x=energy, y=intensity, mode='lines', name=filename), secondary_y=False)
            else:
                fig.add_trace(go.Scatter(x=prange, y=intensity, mode='lines', name=filename), secondary_y=False)
        all_intensity = np.array(all_intensity)

        @render.download(filename="spectrum.csv")
        def save_spectrum():
            filenamestr = ""
            for filename in filenames:
                filenamestr += f"Intensity [64 bit] {filename}, "
            filenamestr = filenamestr.rstrip(", ")
            if mode == "px":
                yield f"Pixel Number, {filenamestr}\n"
                for pix, intens in zip(prange, all_intensity.T):
                    yield f"{pix},{', '.join(map(str, intens))}\n"

            elif mode == "wl":
                yield f"Wavelength [nm], {filenamestr}\n"
                for wl, intens in zip(wavelength, all_intensity.T):
                    print(intens)
                    yield f"{wl}, {', '.join(map(str, intens))}\n"
            else:
                yield f"Energy [eV], {filenamestr}\n"
                for en, intens in zip(energy, all_intensity.T):
                    yield f"{en}, {', '.join(map(str, intens))}\n"

        if input.pc():
            try:
                i_reference = filenames.index(input.reference())
            except ValueError:
                i_reference = 0
            ui.update_select("reference", choices=filenames, selected=filenames[i_reference])
            diff_peaks, diff_peak_heights = unique_peaks(allpeaks, allpeakheights, i_reference,
                                                         input.distance(), input.height_threshold() / 100,
                                                         input.common())

            for peak_pos, peak_amp in zip(diff_peaks, diff_peak_heights):
                if mode == "wl":
                    x = wavelength[peak_pos]
                elif mode == "ev":
                    x = energy[peak_pos]
                else:
                    x = peak_pos
                if input.uselog():
                    y = np.log10(peak_amp) * 1.005
                    y_offset = 0
                    text = "↓"
                else:
                    y = peak_amp
                    y_offset = -40
                    text = ""

                fig.add_annotation(
                    x=x, y=y,
                    text=text,
                    font_size=40,
                    showarrow=True,
                    arrowhead=5,
                    arrowwidth=2,
                    arrowcolor='black',
                    ax=0,
                    ay=y_offset,
                )

        if input.nist():
            if mode != "px":
                # Define which element should be searched for in the NIST database
                element = input.element()
                element = element[0].upper() + element[1:].lower()

                # Get dataframe with data only of chosen element
                el_df = df_nist[df_nist['element'] == element].copy()
                if len(el_df) == 0:
                    raise ValueError("Unknown chemical symbol!")
                # get dataframe with data only in given wavelength range
                el_wl_df = el_df[(el_df['wavelength'] >= 5) & (el_df['wavelength'] <= 25)]

                # Ensure the width falls within the specified range
                bar_width = 0.01

                # Plot NIST peaks
                if mode == "wl":
                    fig.add_trace(go.Bar(x=el_wl_df['wavelength'], y=el_wl_df['intens_numeric'],
                                         width=bar_width, marker_color="black", opacity=0.7, name="NIST Lines"),
                                  secondary_y=True)
                elif mode == "ev":
                    bar_width *= 10
                    fig.add_trace(go.Bar(x=h_planck * c / (el_wl_df['wavelength'] * 1e-9), y=el_wl_df['intens_numeric'],
                                         width=bar_width, marker_color="black", opacity=0.7, name="NIST Lines"),
                                  secondary_y=True)
                if input.uselog():
                    fig.update_yaxes(type='log', title="NIST Relative Line Intensity (log)", secondary_y=True,
                                     tickfont_size=18, title_font_size=20)
                else:
                    fig.update_yaxes(title_text="NIST Relative Line Intensity", secondary_y=True, tickfont_size=18,
                                     title_font_size=20)

        if input.uselog():
            fig.update_yaxes(type='log', title="Intensity (log) [16bit]", tickfont_size=18, title_font_size=20,
                             secondary_y=False)
        else:
            fig.update_yaxes(title="Intensity  [16bit]", range=[0, maxintensity * 1.05], tickfont_size=18,
                             title_font_size=20, secondary_y=False)

        if mode == "wl":
            fig.update_xaxes(title="Wavelength [nm]", range=[5, 20], tickvals=list(range(5, 21)), tickfont_size=18,
                             title_font_size=20)
        elif mode == "ev":
            fig.update_xaxes(title="Energy [eV]", range=[h_planck * c / (20e-9), h_planck * c / (5e-9)],
                             tickfont_size=18, title_font_size=20)

        else:
            fig.update_xaxes(title="Pixel Number", tickfont_size=18, title_font_size=20)

        fig.update_layout(height=input.dimension()[1] - 350, legend_font_size=20,
                          legend_xanchor="right", legend_x=0.9, legend_bgcolor='rgba(0,0,0,0)')

        # Add click event to the plot
        fig.update_layout(clickmode='event+select')
        if len(filedata) <= 1:
            fig.update_layout(showlegend=False)

        def clickedPoints(trace, points, selector):

            if points.point_inds:
                wl = points.xs[0]
                if input.xaxis() == "px":
                    wl = wavelength[wl]
                intensity = points.ys[0]
                filename = points.trace_name
                wavelength_list.append([wl, intensity, filename])
                wavelength_df.set(pd.DataFrame(wavelength_list, columns=get_df_columns(input.xaxis())))

                @render.table
                def clickedPoints():
                    return wavelength_df.get()

            else:
                pass

        # Attach the click event to all traces
        for trace in fig.data:
            trace.on_click(clickedPoints)

        @render.download(filename="clicked_peaks.csv")
        def save():
            df_columns = get_df_columns(input.xaxis())
            yield ", ".join(df_columns) + "\n"
            for index, row in wavelength_df.get().iterrows():
                # Convert each value to string and join them with commas
                yield f"{row[df_columns[0]]}, {row[df_columns[1]]}, {row[df_columns[2]]}\n"

        @reactive.effect
        @reactive.event(input.modal)
        def _():
            if len(wavelength_df.get()) == 0:
                return
            elif input.xaxis() == "ev":
                return
            m = ui.modal(
                ui.div(
                    ui.input_select(
                        "chosen_peak",
                        "Choose a peak:",
                        {str(i): f"Peak {i + 1}: {wl:.5f} nm" for i, wl in
                         enumerate(wavelength_df.get()["Wavelength [nm]"])},
                    ),
                    ui.input_slider("delta_wl", "Wavelength Tolerance", min=0.00, max=1, value=0.1, step=0.01,
                                    post="nm"),
                    ui.input_text_area("chosen_elements", "Input possible elements", ""),
                    ui.output_table("el_candidates"),
                ),
                title="Peak Element Detection",
                easy_close=True,
                footer=None,
            )
            ui.modal_show(m)

        @reactive.effect
        @reactive.event(input.delta_wl, input.chosen_elements, input.chosen_peak)
        def update_candidates():
            if len(wavelength_df.get()) == 0:
                return
            peak_wl = wavelength_df.get()["Wavelength [nm]"].iloc[int(input.chosen_peak())]
            delta_wl = input.delta_wl()
            candidate_df = df_nist[
                (df_nist['wavelength'] >= peak_wl - delta_wl) & (df_nist['wavelength'] <= peak_wl + delta_wl)]

            if not input.chosen_elements() == "":
                chosen_elements = [x.strip() for x in input.chosen_elements().split(",")]
                try:
                    chosen_elements = [element[0].upper() + element[1:].lower() for element in chosen_elements]
                except IndexError:
                    pass
                candidate_df = candidate_df[candidate_df['element'].isin(chosen_elements)]

            candidate_df = candidate_df.sort_values(by='intens_numeric', ascending=False)
            candidate_df = candidate_df.rename(
                columns={'element': 'Element', 'intens_numeric': 'Relative Intensity', 'wavelength': 'Wavelength [nm]'})
            candidate_df = candidate_df.drop_duplicates()

            @render.table
            def el_candidates():
                return candidate_df

        @reactive.effect
        @reactive.event(input.xaxis)
        def update_df_columns():
            wavelength_df.set(pd.DataFrame(columns=get_df_columns(input.xaxis())))

        return fig

    # @render.image
    # def image():
    #     if not input.filenames():
    #         return

    #     filenames = [x['name'] for x in input.filenames()]
    #     images_info = []

    #     for i, file_info in enumerate(input.filenames()):
    #         filepath = file_info['datapath']
    #         with Image.open(filepath) as img:
    #             png_path = filepath.replace('.tif', f'_{i}.png')
    #             img.save(png_path, format="PNG")
    #             images_info.append({
    #                 "src": png_path,
    #                 "width": "90%",
    #                 "style": "margin-left: 75px;"
    #             })

    #     return images_info
    @render.image
    def image():
        if not input.filenames():
            # raise NameError("Please select a valid .tif file")
            return

        def normalize_img(img):
            image_array = np.array(img)
            # Normalize intensities to the range [0, 1]
            max_intensity = image_array.max()
            normalized_image_array = image_array / max_intensity * 255
            img = Image.fromarray(normalized_image_array.astype(np.uint8))
            return img

        filenames = [x['name'] for x in input.filenames()]
        try:
            i_image = filenames.index(input.select_image())
        except ValueError:
            i_image = 0
        ui.update_select("select_image", choices=filenames, selected=filenames[i_image])
        filepath = input.filenames()[i_image]['datapath']

        with Image.open(filepath) as img:

            if input.panel_sqrt():
                image_array = np.array(img)
                # Apply square root transformation
                sqrt_image_array = np.sqrt(image_array)

                img = Image.fromarray(sqrt_image_array.astype(np.uint8))

            if input.normalize():
                img = normalize_img(img)

            png_path = filepath.replace('.tif', '.png')
            img.save(png_path, format="PNG")

        return {"src": png_path, "width": "90%", "style": "margin-left: 75px;"}


app = App(app_ui, server)
