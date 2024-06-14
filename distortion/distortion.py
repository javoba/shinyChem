#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri May  3 20:23:39 2024

@author: vonballmoos
"""
import plotly.graph_objs as go
from PIL import Image
import numpy as np
from shinywidgets import output_widget, render_widget
from shiny import App, ui, render, reactive
from scipy.signal import find_peaks, peak_prominences

prominence_factor = 0.01

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
            ui.input_select("material", "Choose a material:",
                            {
                                "LiF": "LiF", "Al": "Al", "Ni": "Ni"
                            },
                            ),
            ui.input_slider("prominence_factor", "Prominence factor of peak detection", 0.1, 99.9, 5, step=0.1, post="%"),
            ui.input_checkbox("uselog", "Use log scale", False),
            ui.input_text_area("p", "Peak positions", rows=15),
            ui.download_button("save", "Save peaks"),
            width="600px",
        ),
        ui.h1("Peak Offset"),
        output_widget("plot_spectrum"),
        output_widget("plot_pixeldiff"),
    ),
    title="Peak Distortion"
)


def getpeaks(filename, prominence_factor):
    # Load the image and get its dimensions
    image = Image.open(filename)
    width, height = image.size
    data = np.array(image)

    # Take the mean of the intensities of each column
    intensity = np.mean(data, axis=0)

    prange = np.array(range(len(intensity)))  # Pixel Number

    prominence_threshold = max(intensity)*prominence_factor
    peaks, _ = find_peaks(intensity, prominence=prominence_threshold)
    peak_heights = intensity[peaks]

    return prange, intensity, peaks.tolist(), peak_heights.tolist()


def server(input, output, session):

    @render_widget
    def plot_spectrum():

        if input.material() == "LiF":
            filenames = ["./LiF/a220d8_0_10.tif", "./LiF/a200d8_-1_15.tif",
                         "./LiF/a180d8_-2_18.tif", "./LiF/a160d8_-3_22.tif", "./LiF/a140d8_-4_25.tif"]
        elif input.material() == "Al":
            filenames = ["./Al/a300d8_-0_0.tif", "./Al/a0d8_-1_9.tif", "./Al/a0d8_-2_13.tif",
                         "./Al/a0d8_-3_17.tif", "./Al/a0d8_-4_20.tif", "./Al/a0d8_-5_24.tif", "./Al/a0d8_-6_26.tif"]
        elif input.material() == "Ni":
            filenames = ["./Ni/a240d8_-0_2.tif", "./Ni/a240d8_-1_6.tif",
                         "./Ni/a210d8_-2_11.tif", "./Ni/a210d8_-3_13.tif", "./Ni/a210d8_-4_14.tif"]
        else:
            raise NameError("How did you get here?")

        allpeaks = []
        allpeakheights = []
        spectra = []

        for filename in filenames:
            prange, intensity, peaks, peak_heights = getpeaks(filename, input.prominence_factor()/100)
            allpeaks.append(peaks)
            allpeakheights.append(peak_heights)
            spectra.append([prange, intensity])

        peakgroups = []

        for peak0 in allpeaks[0]:
            pkgroup = np.zeros(len(filenames))
            pkgroup[0] = peak0
            pkdiff = np.zeros(len(filenames)-1)
            for i, secpeaks in enumerate(allpeaks[1:]):
                for p1 in secpeaks:
                    if (p1 - pkgroup[i]) < 15 and (p1 - pkgroup[i]) >= -1:
                        pkgroup[i+1] = p1
                        break

            peakgroups.append(pkgroup)

        peakgroups = np.array(peakgroups)
        pstring = ""
        for i in range(len(peakgroups.T)):
            pstring += f"{i}mm\t"
        pstring += "\n"
        for peak in peakgroups:
            for p in peak:
                pstring += f"{p:>6.0f}\t"
            pstring.rstrip("\t")
            pstring += "\n"
        pstring.rstrip("\n")
        ui.update_text_area("p", value=pstring)

        maxintensity = 0
        fig = go.Figure()
        for filename, [[peaks, peak_heights], [prange, intensity]] in zip(filenames, zip(zip(allpeaks, allpeakheights), spectra)):
            maxintensity = max(maxintensity, max(intensity))

            fig.add_trace(go.Scatter(x=prange, y=intensity, mode='lines', name=filename))
            if not input.uselog():
                for peak_pos, peak_amp in zip(peaks, peak_heights):
                    fig.add_annotation(
                        x=peak_pos, y=peak_amp,
                        text=f'{peak_pos:.0f}',
                        showarrow=True,
                        arrowhead=3,
                        arrowwidth=1,
                        ax=0,
                        ay=-30,
                    )

        if input.uselog():
            fig.update_yaxes(type='log', title="Intensity (log)  [16bit]", tickfont_size=18, title_font_size=20)
        else:
            fig.update_yaxes(title="Intensity  [16bit]", range=[0, maxintensity*1.1], tickfont_size=18, title_font_size=20)
        fig.update_xaxes(title="Pixel Number", tickfont_size=18, title_font_size=20)
        fig.update_layout(legend_font_size=20, legend_xanchor="right", legend_x=1,
                          legend_bgcolor='rgba(0,0,0,0)', height=(input.dimension()[1]-200)/2)
        if len(filenames) <= 1:
            fig.update_layout(showlegend=False)
        return fig

    @render_widget
    def plot_pixeldiff():
        peaks = []

        lines = input.p().rstrip("\n").split("\n")
        for line in lines[1:]:
            peaks.append([int(p) for p in line.rstrip("\t").split("\t")])
        peaks = np.array(peaks)

        peakdiffs = []
        for p in peaks:
            pkdiff = np.repeat(-999, len(peaks.T))
            for i, p_i in enumerate(p[1:]):
                if p_i != 0:
                    pkdiff[i] = p_i-p[0]
            peakdiffs.append(pkdiff)
        peakdiffs = np.array(peakdiffs)
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=[10], y=[0], mode='markers', showlegend=False, marker_color="rgba(0,0,0,0)"))
        for i, p in enumerate(peakdiffs.T):
            peakpos = peaks[:, 0][p != -999]
            p = p[p != -999]
            fig.add_trace(go.Scatter(x=peakpos, y=p, mode='lines+markers', marker_symbol="cross",
                          marker_opacity=0.7, marker_size=10, name=f"Position - {i+1} mm"))

        fig.update_xaxes(title="Pixel Number at central position", tickfont_size=18, title_font_size=20, range=[0, 2047])
        fig.update_yaxes(title="Pixel offset", tickfont_size=18, title_font_size=20)
        fig.update_layout(legend_font_size=20, legend_x=1, legend_xanchor="right",
                          legend_bgcolor='rgba(0,0,0,0)', height=(input.dimension()[1]-200)/2)
        return fig

    @render.download(filename="peaks.tsv")
    def save():
        peaks = []

        lines = input.p().rstrip("\n").split("\n")
        for line in lines[1:]:
            peaks.append([int(p) for p in line.rstrip("\t").split("\t")])
        peaks = np.array(peaks)

        for i in range(len(peaks.T)):
            yield f"{i}mm\t"
        yield "\n"

        for p in peaks:
            yield "\t".join(map(lambda x: f"{x:.0f}", p))
            yield "\n"
        # for i, p in enumerate(peaks.T):
        #     yield f"{i} mm\n"
        #     yield "\n".join(map(lambda x: f"{x:.0f}", p))
        #     yield "\n\n"


app = App(app_ui, server)
