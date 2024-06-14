import pandas as pd
import numpy as np
import plotly.graph_objs as go

from shinywidgets import output_widget, render_widget
from shiny import App, ui, render, reactive

basedir = r"G:\Limit\vbja\XRD\New"

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
            ui.input_file("filenames", "Select data files", multiple="True"),
            ui.download_button("save", "Save data"),
            ui.input_action_button("plot_button", "Generate Plot"),  # New button for plot rendering

            width="500px",
        ),
        ui.div(
            ui.h1("RSM Plot"),
            output_widget("plot_RSM"),
            style="display: flex; flex-direction: column;"
        )
    ),
    title="RSM Plot",
)


def get_df(files, filenames):
    df_combined = pd.DataFrame()
    for file, filename in zip(files, filenames):
        y = float(filename.split("=")[1].replace(".xy", ""))
        df = pd.read_csv(file, sep=" ", header=None, names=["x", "z"])
        df['y'] = y
        df_combined = pd.concat([df_combined, df], ignore_index=True)
        df_combined = df_combined[['x', 'y', 'z']]
    return df_combined


def server(input, output, session):
    @render_widget
    @reactive.event(input.plot_button)  # React to plot button click
    def plot_RSM():
        files = [file['datapath'] for file in input.filenames()]
        filenames = [file['name'] for file in input.filenames()]

        df_combined = get_df(files, filenames)
        # Create a pivot table to prepare data for contour plot
        contour_data = pd.pivot_table(df_combined, values='z', index='y', columns='x')

        # Define the number of discrete colors and their boundaries
        num_colors = 6
        z_min, z_max = contour_data.values.min(), contour_data.values.max()
        contour_levels = np.linspace(z_min, z_max, num_colors)

        custom_colors = ['white', 'black', 'blue', 'yellow', 'red', 'white']

        # Create a custom colorscale with discrete colors
        colorscale = [[val, custom_colors[i]] for i, val in enumerate(np.linspace(0, 1, num_colors))]

        # Create a contour plot with Plotly Graph Objects
        fig = go.Figure()

        fig.add_trace(go.Contour(
            z=contour_data.values,
            x=contour_data.columns,
            y=contour_data.index,
            contours=dict(
                showlines=False,  # Show contour lines between bins
                start=z_min,
                end=z_max,
                size=(z_max - z_min) / (num_colors - 1),  # Interval between colors
            ),
            colorscale=colorscale,
            colorbar=dict(
                title='z value',
                tickvals=contour_levels,
                ticktext=[f'{val:.2f}' for val in contour_levels],
                tickmode='array'
            )
        ))

        # Set labels
        fig.update_layout(
            xaxis_title='X',
            yaxis_title='Y',
            height=input.dimension()[1] - 180
        )
        return fig

    @render.download(filename="RSMdata.csv")
    def save():
        files = [file['datapath'] for file in input.filenames()]
        filenames = [file['name'] for file in input.filenames()]

        df_combined = get_df(files, filenames)

        yield df_combined.to_csv(index=False)


app = App(app_ui, server)
