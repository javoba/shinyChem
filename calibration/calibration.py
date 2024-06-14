"""
Created on Fri Nov 10 13:25:51 2023

@author: vbja
"""
import numpy as np
from shinywidgets import output_widget, render_widget
from shiny import App, ui, render, reactive
import plotly.graph_objs as go

known_pixels_init = [250, 394, 632, 1036, 1050, 1130, 1196, 1537, 1555, 1892,
                     1423, 1680, 602, 614, 744, 973, 1159, 1307, 1497, 1617]  # , 1017, 1136]
known_wavelengths_init = [5.5375, 6.7943, 8.81632, 11.7853, 11.8964, 12.553, 13.084, 16.0072, 16.1688, 19.05695,
                          15.1546, 17.2169, 8.58162, 8.6457, 9.57842, 11.2978, 12.7815, 13.9916, 15.625, 16.72042]  # , 12.19851, 12.9441]

known_pixels_str = '\n'.join(str(pixel) for pixel in known_pixels_init)
known_wavelengths_str = '\n'.join(str(wl) for wl in known_wavelengths_init)

pstr_init = "5e-07x^2 + 0.0067x + 4.4987"


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


def calc_rsquared(x, y, f):
    # Calculate R²
    y_pred = f(np.array(x))

    # Calculate the total sum of squares (TSS)
    y_mean = np.mean(y)
    TSS = np.sum((y - y_mean) ** 2)

    # Calculate the residual sum of squares (RSS)
    RSS = np.sum((y - y_pred) ** 2)

    # Calculate R-squared
    r_squared = 1 - (RSS / TSS)
    return r_squared


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
    ui.input_dark_mode(id="mode"),
    ui.div(
        ui.input_action_button("home", "home", onclick="location.href='https://shinychem.duckdns.org';"),
        style="display:inline-block; position:relative; left:calc(50%);",
    ),
    ui.layout_sidebar(
        ui.sidebar(
            ui.input_slider("degree", "Order of polynomial fitting function", 1, 5, 3),
            ui.card(
                ui.p("Add pixel number - wavelength pairs for polynomial fit:"),
                ui.row(
                    ui.column(6,
                              ui.input_text_area("p", "Pixel Numbers", value=known_pixels_str, rows=5),
                              ),
                    ui.column(6,
                              ui.input_text_area("w", "Wavelengths", value=known_wavelengths_str, rows=5)
                              ),
                ),
                ui.input_action_button("reset", "Reset", width="50%"),
                ui.output_text("polystr"),
            ),

            ui.card(
                ui.p("System parameters (for flat field calibration function)"),
                ui.input_slider("a", "Incident angle α", 80, 90, 87, step=0.01, post="°"),
                ui.input_slider("L", "Imaging distance L", 10, 500, 235, step=0.1, post="mm"),
                ui.input_slider("s", "Size of CCD pixels s", 10, 20, 13.5, step=0.01, post="µm"),
                ui.input_slider("d0", "Groove density 1/d0", 50, 1500, 1200, post="grooves/mm"),
                ui.input_slider("x0", "distance to CCD x0", 20, 40, 27.5, step=0.01, post="mm"),
                ui.input_slider("gamma", "CCD detector tilt γ ", 85, 95, 90, step=0.01, post="°"),
                ui.output_text("di_str"),
            ),
            ui.card(ui.input_text("fct", "User defined polynomial function", value=pstr_init)),
            width="500px",
        ),
        ui.h1("LIXS Wavelength Calibration"),
        output_widget("plot_calibration", width="100%"),
    ),
    title="LIXS Wavelength Calibration",
)


def server(input, output, session):
    @reactive.effect
    @reactive.event(input.reset)
    def reset():
        ui.update_text_area("p", value=known_pixels_str)
        ui.update_text_area("w", value=known_wavelengths_str)

    @render_widget
    def plot_calibration():
        display_height = input.dimension()[1]

        # Define known wavelength - pixel nr. pairs (for different elements)
        #               Al                                         Si          Ti
        known_pixels = [int(px) for px in input.p().rstrip("\n").split("\n")]
        known_wavelengths = [float(wl) for wl in input.w().rstrip("\n").split("\n")]

        # Fit polynomial to wavelength-pixel pairs
        degree = input.degree()  # degree of polynomial
        coefficients = np.polyfit(known_pixels, known_wavelengths, degree)
        polynomial = np.poly1d(coefficients)

        man_polynomial = read_poly(input.fct())

        @render.text
        def polystr():
            coeffstr = ""
            for i, coeff in enumerate(coefficients):
                coeff = f"{coeff:.4e}"
                if coeff.startswith("-"):
                    sign = " - "
                    if i > 0:
                        coeff = coeff.lstrip("-")
                else:
                    sign = " + "
                if i > 0:
                    coeffstr += sign
                coeffdeg = degree - i
                coeffstr += coeff
                if coeffdeg >= 2:
                    coeffstr += f"x^{coeffdeg}"
                elif coeffdeg == 1:
                    coeffstr += f"x"
            return coeffstr

        irange = np.arange(2048)

        def f_di(i):
            x_0 = input.x0()*1e6
            d_0 = 1/input.d0()*1e6  # mm to nm
            alpha = np.deg2rad(input.a())
            L = input.L()*1e6  # mm to nm
            s = input.s()*1e3  # mum to nm
            gamma = np.deg2rad(input.gamma())
            return d_0 * (np.sin(alpha) - (L - np.cos(gamma) * (L*np.cos(gamma) + x_0 + s * i)) / np.sqrt((x_0 + s * i)**2 + (L*np.sin(gamma))**2))

        f_y_di = f_di(irange)

        @render.text
        def di_str():
            x_0 = input.x0()*1e6
            d_0 = 1/input.d0()*1e6  # mm to nm
            alpha = input.a()
            L = input.L()*1e6  # mm to nm
            s = input.s()*1e3  # mum to nm
            gamma = input.gamma()
            return f"{d_0:.3e} (sin({alpha:.2f}) - ({L:.3e} - cos({gamma:.2f}) × ({L:.3e} × cos({gamma:.2f}) + {x_0:.3e} + {s:.3e} × i)) / sqrt(({x_0:.3e} + {s:.3e} × i)^2 + ({L:.3e} × sin({gamma:.2f})^2))"

        # Plot Polynomial
        f_y = polynomial(irange)
        man_f_y = man_polynomial(irange)

        r_squared = calc_rsquared(known_pixels, known_wavelengths, polynomial)
        di_r_squared = calc_rsquared(known_pixels, known_wavelengths, f_di)
        man_r_squared = calc_rsquared(known_pixels, known_wavelengths, man_polynomial)

        fig = go.Figure()

        # Add traces
        fig.add_trace(go.Scatter(x=known_pixels, y=known_wavelengths, mode='markers', marker=dict(
            color='red', size=10), name="Reference Wavelengths"))
        fig.add_trace(go.Scatter(x=irange, y=f_y, mode='lines',
                      name=f"Polynomial Fit of Order {degree} (R<sup>2</sup>={r_squared:.4f})"))

        fig.add_trace(go.Scatter(x=irange, y=f_y_di, mode='lines',
                      name=f"Flat Field Calibration (DOI: 10.1039/D0JA00215A) (R<sup>2</sup>={di_r_squared:.4f})"))

        fig.add_trace(go.Scatter(x=irange, y=man_f_y, mode='lines', name=f"User Defined Polynomial Calibration (R<sup>2</sup>={man_r_squared:.4f})"))

        # Update layout

        fig.update_xaxes(title="Pixel Number", range=[0, 2048], tickfont_size=18, title_font_size=20)
        fig.update_yaxes(title="Wavelength [nm]", tickfont_size=18, title_font_size=20)
        fig.update_layout(height=display_height-180, legend_font_size=20, legend_x=0, legend_bgcolor='rgba(0,0,0,0)')
        return fig


app = App(app_ui, server)
