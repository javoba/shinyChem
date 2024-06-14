#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri May  3 19:59:30 2024

@author: vonballmoos
"""
import pandas as pd
import plotly.graph_objs as go

from shinywidgets import output_widget, render_widget
from shiny import App, ui

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
            ui.input_text("element", "Chemical Symbol", value="Al", width="60px"),
            ui.input_checkbox("uselog", "Use log scale", False),
            ui.input_checkbox("filter", "Show lines that have no intensity in NIST", False),
        ),
        ui.h1("Spectral Lines from NIST Database"),
        ui.input_slider("wl", "Wavelength Range:", min=1, max=200, value=[5, 20], width="100%"),
        output_widget("plot_nist"),
    ),
    title="Nist Lines",
)


def server(input, output, session):
    @render_widget
    def plot_nist():
        # Define which element should be searched for in the NIST database
        element = input.element()
        element = element[0].upper() + element[1:].lower()

        # Read NIST lines
        df = pd.read_pickle('nist_lines.pkl')

        # Get dataframe with data only of chosen element
        el_df = df[df['element'] == element].copy()
        if len(el_df) == 0:
            raise ValueError("Unknown chemical symbol!")
        # get dataframe with data only in given wavelength range
        el_wl_df = el_df[(el_df['wavelength'] >= input.wl()[0]) & (el_df['wavelength'] <= input.wl()[1])]

        wavelength_range = input.wl()[1] - input.wl()[0]
        max_bar_width = 0.5  # Define the maximum width of the bars
        min_bar_width = 0.001  # Define the minimum width of the bars
        normalized_width = (wavelength_range / 200) * max_bar_width  # Adjust 100 to control sensitivity to range

        # Ensure the width falls within the specified range
        bar_width = max(min(normalized_width, max_bar_width), min_bar_width)

        # Plot NIST peaks
        fig = go.Figure()
        if not input.filter():
            el_wl_df = el_wl_df[el_wl_df['intens_numeric'] > 1]
        # Add bar trace
        fig.add_trace(go.Bar(
            x=el_wl_df['wavelength'],
            y=el_wl_df['intens_numeric'],
            width=bar_width
        ))
        fig.update_xaxes(title="Wavelength [nm]", range=input.wl(), tickfont_size=18, title_font_size=20)

        fig.update_layout(showlegend=False, barmode='overlay', height=input.dimension()[1] - 275)

        if input.uselog():
            fig.update_yaxes(type='log', title="Relative Intensity (log)", tickfont_size=18, title_font_size=20)
        else:
            fig.update_yaxes(title="Relative Intensity", tickfont_size=18, title_font_size=20)

        return fig


app = App(app_ui, server)
