# -*- coding: utf-8 -*-
"""
Created on Fri Nov  3 10:49:22 2023

@author: vbja
"""
from shinywidgets import output_widget, render_widget
from shiny import App, ui, reactive, render
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from sortedcontainers import SortedDict
from PIL import Image

alpha = np.deg2rad(87)  # Incident angle (rad)
d_0 = 1 / 1200 * 1e6  # Groove density [nm]
R = 5649  # Curvature [mm]
r = 237  # Incident length [mm]
b_2 = -20  # ruling parameter [-]
D = 50  # width of grating [m]

colorscale = [[0, 'violet'], [0.025, 'blue'], [0.1, 'green'], [0.25, 'yellow'],
              [0.5, 'orange'], [1, 'red']]  # Define colorscale for wavelengths


def beam_width(r2, beta, gamma, D, L, x_rel):
    y = r2 * np.sin(beta)
    L2 = L - np.cos(gamma) * x_rel

    b = np.sqrt(D ** 2 / 4 + r2 ** 2 + D * r2 * np.sin(beta))
    delta = np.arcsin(r2 * np.cos(beta) / b)
    a = np.sqrt(b ** 2 + D ** 2 - 2 * b * D * np.cos(delta))
    theta = np.arcsin(D * np.sin(delta) / a)
    return np.abs(np.sin(theta) * (y - L2) / (np.cos(theta + delta) * np.sin(delta + gamma)))


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
    ui.input_dark_mode(),
    ui.div(
        ui.input_action_button("home", "home", onclick="location.href='https://shinychem.duckdns.org';"),
        style="display:inline-block; position:relative; left:calc(50%);",
    ),
    ui.layout_sidebar(
        ui.sidebar(
            ui.p("Grating presets"),
            ui.row(
                ui.column(4, ui.input_action_button("g1", "5-20nm")),
                ui.column(4, ui.input_action_button("g2", "20-80nm")),
                ui.column(4, ui.input_action_button("g3", "50-200nm")),
            ),
            ui.input_action_button("hold", "Hold current focal curve data"),
            ui.card(
                ui.p("Grating Parameters"),
                ui.input_slider("d_0", "Groove density 1/d0", 50, 1500, 1200, post="grooves/mm"),
                ui.input_slider("alpha", "Incident angle", 80, 90, 87, step=0.01, post="°"),
                ui.input_slider("R", "Curvature R ", 1, 10, 5.65, step=0.01, post="m"),
                ui.input_slider("r", "Incident Length r", 100, 500, 237, step=0.1, post="mm"),
                ui.input_slider("b_2", "Ruling Parameter b2", -50, 0, -20, step=0.01),
            ),

            ui.input_file("bg_filename", "Select a .tif file as the background of the spectrum", accept=".tif"),
            ui.input_checkbox("panel_sqrt", "Take square root of image intensities", False),

            ui.input_text_area("wl", "Wavelengths"),
            ui.card(
                ui.p("CCD Parameters"),
                ui.input_slider("ccd_d", "CCD Diameter [mm]", 10, 150, 25.3, step=0.1),
                ui.input_slider("x0", "CCD Offset x0[mm]", 0, 150, 28.8, step=0.1),
                ui.input_slider("L", "Distance to grating L [mm]", 150, 300, 237, step=0.1),
                ui.input_slider("gamma", "CCD angle [°]", 45, 135, 90, step=0.1),
            ),
            width="500px",
        ),
        ui.div(
            ui.h1("Grating Focal Curve"),
            ui.div(
                output_widget("plot_grating"),
                style="margin-bottom: 20px;"  # Adds space below the first widget
            ),
            output_widget("plot_spectrum"),
            style="display: flex; flex-direction: column;"
        )
    ),
    title="Grating"
)


def server(input, output, session):
    @reactive.effect
    @reactive.event(input.g1)
    def preset1():
        ui.update_slider("d_0", value=1200)
        ui.update_slider("alpha", value=87)
        ui.update_slider("R", value=5.65)
        ui.update_slider("r", value=237)
        ui.update_slider("b_2", value=-20)

    @reactive.effect
    @reactive.event(input.g2)
    def preset2():
        ui.update_slider("d_0", value=300)
        ui.update_slider("alpha", value=87)
        ui.update_slider("R", value=5.65)
        ui.update_slider("r", value=237)
        ui.update_slider("b_2", value=-20)

    @reactive.effect
    @reactive.event(input.g3)
    def preset3():
        ui.update_slider("d_0", value=120)
        ui.update_slider("alpha", value=87)
        ui.update_slider("R", value=5.65)
        ui.update_slider("r", value=237)
        ui.update_slider("b_2", value=-20)

    stored_lambda = reactive.Value(pd.DataFrame([], columns=["y", "x", "wavelength"]))
    lambda_current = reactive.Value(pd.DataFrame([], columns=["y", "x", "wavelength"]))

    @reactive.effect
    @reactive.event(input.hold)  # React to plot button click
    def hold():
        if stored_lambda.get().empty:
            stored_lambda.set(lambda_current.get())
        else:
            stored_lambda.set(pd.concat([stored_lambda.get(), lambda_current.get()], ignore_index=True))

    @render_widget
    def plot_grating():
        if input.wl() == "":
            chosen_wavelengths = []
        else:
            chosen_wavelengths = [float(wl.replace(" ", "")) for wl in input.wl().split(",")]

        x_sel = np.zeros_like(chosen_wavelengths)
        y_sel = np.zeros_like(chosen_wavelengths)

        # lambda_list = np.arange(1, 200.1, 0.1)  # Wavelength [nm]
        lambda_list = np.logspace(0, np.log10(200), 1500)
        x = np.zeros_like(lambda_list)
        y = np.zeros_like(lambda_list)

        alpha = np.deg2rad(input.alpha())
        d_0 = 1 / input.d_0() * 1e6
        R = input.R() * 1000
        r = input.r()
        b_2 = input.b_2()
        fig = go.Figure()

        x0 = input.x0()
        L = input.L()
        ccd_d = input.ccd_d()
        gamma = np.deg2rad(input.gamma())

        linex = [L, L - np.cos(gamma) * ccd_d]
        liney = [x0, x0 + np.sin(gamma) * ccd_d]
        # for alpha in alpha_list:
        for i, l in enumerate(lambda_list):
            beta = np.arcsin(np.sin(alpha) - l / d_0)
            num = R * r * np.cos(beta) ** 2
            den = r * (np.cos(alpha) + np.cos(beta) - 2 * (b_2) * l / d_0) - R * (np.cos(alpha)) ** 2
            r2 = num / den
            x[i] = r2 * np.cos(beta)
            y[i] = r2 * np.sin(beta)

        for i, l in enumerate(chosen_wavelengths):
            beta = np.arcsin(np.sin(alpha) - l / d_0)
            num = R * r * np.cos(beta) ** 2
            den = r * (np.cos(alpha) + np.cos(beta) - 2 * (b_2) * l / d_0) - R * (np.cos(alpha)) ** 2
            r2 = num / den
            x_sel[i] = r2 * np.cos(beta)
            y_sel[i] = r2 * np.sin(beta)

        # Update lambda_current with new data, including wavelength
        lambda_current.set(pd.DataFrame({'y': y, 'x': x, 'wavelength': lambda_list}))

        # If stored_lambda is not empty, plot the data
        if not stored_lambda.get().empty:
            fig.add_trace(go.Scatter(
                x=stored_lambda.get()['y'],
                y=stored_lambda.get()['x'],
                marker=dict(
                    color=stored_lambda.get()['wavelength'],
                    colorscale=colorscale,
                    colorbar=dict(
                        title="Wavelength [nm]",
                    ),
                ),
                mode='markers',
                opacity=0.6,
                hoverinfo='text',
                text=[f'{x_val:.3f} mm, {y_val:.3f} mm, {wavelength:.3f} nm' for x_val, y_val, wavelength in
                      zip(stored_lambda.get()['y'], stored_lambda.get()['x'], stored_lambda.get()['wavelength'])]
            ))

        fig.add_trace(go.Scatter(x=y, y=x,
                                 marker=dict(
                                     color=lambda_list,
                                     colorscale=colorscale,
                                     colorbar=dict(
                                         title="Wavelength [nm]",
                                     ),
                                 ),
                                 mode='markers',
                                 opacity=0.6,
                                 hoverinfo='text',
                                 text=[f'{x_val:.3f} mm, {y_val:.3f} mm, {wavelength:.3f} nm' for
                                       x_val, y_val, wavelength in zip(y, x, lambda_list)]))

        fig.add_trace(go.Scatter(x=y_sel, y=x_sel,
                                 marker=dict(
                                     color="grey",
                                     size=12,
                                 ),
                                 mode='markers',
                                 opacity=0.6,
                                 hoverinfo='text',
                                 text=[f'{x_val:.3f} mm, {y_val:.3f} mm, {wavelength:.3f} nm' for
                                       x_val, y_val, wavelength in zip(y, x, chosen_wavelengths)]))

        fig.add_trace(go.Scatter(x=linex, y=liney, mode="lines", marker_color="black", line_width=10))

        fig.update_xaxes(title_text="Y [mm]", tickfont_size=18, title_font_size=20)
        fig.update_yaxes(title_text="X [mm]", tickfont_size=18, title_font_size=20)

        fig.update_layout(height=(input.dimension()[1] - 500), showlegend=False)

        return fig

    @render_widget
    def plot_spectrum():

        def normalize_img(img):
            image_array = np.array(img)
            # Normalize intensities to the range [0, 1]
            max_intensity = image_array.max()
            normalized_image_array = image_array / max_intensity * 255
            img = Image.fromarray(normalized_image_array.astype(np.uint8))
            return img

        layout = go.Layout(hovermode="x")
        fig = go.FigureWidget(layout=layout)

        if input.bg_filename():
            filepath = input.bg_filename()[0]['datapath']

            image = Image.open(filepath)
            if input.panel_sqrt():
                image_array = np.array(image)
                # Apply square root transformation
                sqrt_image_array = np.sqrt(image_array)

                image = Image.fromarray(sqrt_image_array.astype(np.uint8))

            image = normalize_img(image)

            fig.update_layout(images=[dict(
                source=image,
                xref="paper", yref="paper",
                x=0, y=1,
                sizex=1, sizey=1,
                xanchor="left", yanchor="top"
            )])

        xrange = np.arange(0, 2048)
        yrange = np.repeat(0.5, len(xrange))
        fig.add_trace(go.Scatter(x=xrange, y=yrange, mode="lines", line_color="rgba(0,0,0,0)",
                                 hoverinfo='text',
                                 text=xrange))

        if input.wl() == "":
            chosen_wavelengths = []
        else:
            chosen_wavelengths = [float(wl.replace(" ", "")) for wl in input.wl().split(",")]

        alpha = np.deg2rad(input.alpha())
        d_0 = 1 / input.d_0() * 1e6
        R = input.R() * 1000
        r = input.r()
        b_2 = input.b_2()
        gamma = np.deg2rad(input.gamma())
        L = input.L()
        ccd_d = input.ccd_d()
        x0 = input.x0()
        s = ccd_d / 2048  # pixel size

        chosen_wavelengths_sel = []
        x_sel = []
        beam_widths = []

        def wl_to_r2(l):
            beta = np.arcsin(np.sin(alpha) - l / d_0)
            num = R * r * np.cos(beta) ** 2
            den = r * (np.cos(alpha) + np.cos(beta) - 2 * (b_2) * l / d_0) - R * (np.cos(alpha)) ** 2
            r2 = num / den
            return r2, beta

        def wl_to_x(l):
            r2, beta = wl_to_r2(l)
            return r2 * np.cos(beta)

        lambda_list = np.logspace(0, np.log10(200), 1500)
        px_to_wl_dict = SortedDict()
        for l in lambda_list:
            r2, beta = wl_to_r2(l)
            x = r2 * np.cos(beta)
            px = (x - x0) / np.sin(gamma) / s
            px_to_wl_dict[px] = l

        # Function to get the closest value if the exact key is not found
        def get_closest_value(d, key):
            if key in d:
                return d[key]
            else:
                pos = d.bisect_left(key)
                if pos == 0:
                    return d[d.iloc[0]]
                if pos == len(d):
                    return d[d.iloc[-1]]
                before = d.iloc[pos - 1]
                after = d.iloc[pos]
                if abs(before - key) <= abs(after - key):
                    return d[before]
                else:
                    return d[after]

        for l in chosen_wavelengths:
            r2, beta = wl_to_r2(l)
            x = r2 * np.cos(beta)
            if x >= x0 and x <= x0 + np.sin(gamma) * ccd_d:
                x_rel = (x - x0) / np.sin(gamma)
                x_sel.append(x_rel / s)
                beam_widths.append(beam_width(r2, beta, gamma, D, L, x_rel))
                chosen_wavelengths_sel.append(l)

        # beam_widths = [max(1, w) for w in np.array(beam_widths) / s]
        beam_widths = np.array(beam_widths) / s

        fig.add_trace(go.Bar(
            x=x_sel,
            y=[1] * len(x_sel),  # y-axis values are always 1
            width=beam_widths,  # width of the bars are the beam_widths
            marker=dict(
                color=chosen_wavelengths_sel,
                colorscale=colorscale,

                cmin=0,
                cmax=200,
            ),
            hoverinfo='text',
            text=[f'{x_val:.0f} pixels, {width:.2f} pixels, {wavelength:.3f} nm' for x_val,
                                                                                     width, wavelength in
                  zip(x_sel, beam_widths, chosen_wavelengths_sel)],
            textposition='none'
        ))

        fig.update_xaxes(title_text="Pixel Number", range=[0, 2047], tickfont_size=18, title_font_size=20)
        fig.update_yaxes(title_text="Intensity", range=[0, 1.05], tickfont_size=18, title_font_size=20)

        fig.update_layout(showlegend=False, height=200)

        def clickedPoints(trace, points, selector):
            if points.point_inds:
                if points.trace_name == "trace 0":
                    px = points.xs[0]
                    wl = get_closest_value(px_to_wl_dict, px)

                    sel_wl = input.wl()
                    sel_wl += f", {wl:.5f}"
                    sel_wl = sel_wl.lstrip(", ")
                    ui.update_text("wl", value=sel_wl)

        # Attach the click event to all traces
        for trace in fig.data:
            trace.on_click(clickedPoints)

        return fig


app = App(app_ui, server)
if __name__ == "__main__":
    app.run()
