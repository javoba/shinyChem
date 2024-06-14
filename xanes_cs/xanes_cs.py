# -*- coding: utf-8 -*-
"""
Created on Fri May 24 13:01:13 2024

@author: vbja
"""

import requests
from bs4 import BeautifulSoup
import os
import re
import json
import numpy as np
import pickle
from scipy import signal

from shiny import App, ui, render, reactive
from shinywidgets import output_widget, render_widget

import pathlib as pl
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

import scipy.fftpack as spfft
import cvxpy as cvx

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
    ui.panel_title("Compressive Sensing for XANES "),
    ui.navset_tab(
        ui.nav_panel("XDI Data Download",
                     ui.layout_sidebar(
                         ui.panel_sidebar(
                             ui.input_text("XDI_filename", "Enter Filename of XDI Data File", value="xdi_data.object"),
                             ui.input_action_button("start_process",
                                                    "Redownload XDI Data from https://xaslib.xrayabsorption.org"),
                             ui.output_ui("progress_bar")
                         ),
                         ui.panel_main(
                             output_widget("plot_XDI"),
                         )
                     )
                     ),
        ui.nav_panel("K-Space Visualisation",
                     ui.panel_main(
                         output_widget("kSpace"),
                     )

                     ),
        ui.nav_panel("R-Space Visualisation",
                     ui.panel_main(
                         output_widget("rSpace"),
                     )

                     ),
        ui.nav_panel("Apply Compressive Sensing",
                     ui.layout_sidebar(
                         ui.panel_sidebar(
                             ui.input_file("ex_filename", "Select .csv file of XDI measurement", accept=".csv"),
                             ui.input_slider("undersampling_ex", "Undersampling", 1, 99, 45, post="%")
                         ),
                         ui.panel_main(
                             output_widget("plot_undersampled"),
                         )
                     )

                     ),
        ui.nav_panel("Compare Errors of Different Solvers",
                     ui.layout_sidebar(
                         ui.panel_sidebar(
                             ui.input_file("meas_filename", "Select .csv file of XDI measurement", accept=".csv"),
                             ui.input_slider("rep", "Repetitions", 1, 100, 10),
                             ui.input_slider("undersampling_comp", "Undersampling", 1, 100, 45, post="%"),
                             ui.input_action_button("start_cs", "Apply compressive sensing"),
                             ui.output_ui("progressbar_cs")
                         ),
                         ui.panel_main(
                             output_widget("compareSolvers"),
                         )
                     )

                     ),
    ),
    title="Compressive Sensing for XANES",
)


def server(input, output, session):
    output_dir = './output_data'
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    labs = ['a) Co 15%', 'b) Co 30%', 'c) Co 45%', 'd) Co 100%']
    labs_xposi = {
        0: 0.455,
        1: 1,
        2: 0.455,
        3: 1
    }

    labs_yposi = {
        0: 0.99,
        1: 0.99,
        2: 0.43,
        3: 0.43
    }

    @reactive.Effect
    @reactive.event(input.start_process)
    def process_data():
        filename = input.XDI_filename()
        xdi_data = {}
        total_spectra = 257

        with ui.Progress(min=1, max=total_spectra + 1) as p:
            p.set(message="Calculation in progress")

            for n in range(1, total_spectra + 1):
                p.set(n, message="Downloading Data", detail=f"{n} of {total_spectra}")

                response = requests.get(f'https://xaslib.xrayabsorption.org/spectrum/{n}/')
                soup = BeautifulSoup(response.text, 'html.parser')
                script = soup.find(id='xasplot').contents[1]
                name = soup.find('div', {'class': 'subtitle'}).text.rstrip('\n').split(':')[1].strip()

                # get javascript object inside the script
                model_data = re.search(r"var graph = ({.*?});", script.text, flags=re.S)
                model_data = model_data.group(1)

                obj = json.loads(model_data)
                x_vals = np.array(obj['data'][0]['x'])
                y_vals = np.array(obj['data'][0]['y'])
                peaks, _ = signal.find_peaks(y_vals, prominence=0.05, height=0.7)
                xdi_data[name] = {'x_vals': x_vals, 'y_vals': y_vals, 'x_peaks': x_vals[peaks],
                                  'y_peaks': y_vals[peaks]}

        with open(f'{filename}', 'wb') as fileObj:
            pickle.dump(xdi_data, fileObj)

        return "Done computing!"

    @render_widget
    def plot_XDI():
        colors = ['red', 'blue', 'brown', 'green', 'skyblue', 'orange']
        i = 250
        p = 0

        mat_list = {
            'V_foil': 'Vanadium (V)',
            'cro2_rt_001': 'Chromium-Oxide (CrO2)',
            'Mn3O4_rt_01': 'Manganese-Oxide (Mn3O4)',
            'co_metal_rt': 'Cobalt (Co)',
            'Ni_metal_rt_01': 'Nickle (Ni)',
            'Cu_Foil_rt_2016Foils_13IDE_01': 'Copper (Co)'
        }

        with open(input.XDI_filename(), 'rb') as f:
            xdi_data = pickle.load(f)

        fig = go.Figure()
        xmax = 0
        ymax = 0
        for x in xdi_data:
            if x in mat_list.keys():
                data = xdi_data[x]['x_vals'] - xdi_data[x]['x_vals'].min()
                dx = np.diff(data)
                dx = np.diff(dx)
                point = np.argmax(np.abs(dx))
                point2 = np.argmax(np.abs(dx)[np.argmax(np.abs(dx)) + 1:]) + point + 1

                xmax = max(xmax, max(data))
                ymax = max(ymax, len(xdi_data[x]['x_vals']))

                fig.add_trace(
                    go.Scatter(
                        x=data,
                        y=np.arange(len(xdi_data[x]['x_vals'])),
                        mode='lines',
                        line=dict(color=colors[p]),
                        name=mat_list[x]
                    )
                )
                fig.add_trace(
                    go.Scatter(
                        x=[data[point], data[point2]],
                        y=[point, point2],
                        mode='markers',
                        marker=dict(color=colors[p],
                                    size=14),
                        showlegend=False
                    )
                )

                p += 1
            if i == 0:
                break
            i -= 1

        fig.update_xaxes(title_text="ΔE (E - E<sub>min</sub>) (eV)", range=[0, xmax * 1.05], tickfont_size=18,
                         title_font_size=20)
        fig.update_yaxes(title_text="Cumulative number of data points", range=[0, ymax * 1.05], tickfont_size=18,
                         title_font_size=20)
        fig.update_layout(height=(input.dimension()[1] - 180), legend_font_size=20,
                          legend_xanchor="right", legend_x=1, legend_bgcolor='rgba(0,0,0,0)')

        return fig

    @render_widget
    def kSpace():
        paths_k = [x for x in pl.Path('.').glob('Co_Data/*/*k*')]
        names_k = [x.stem for x in pl.Path('.').glob('Co_Data/*/*k*')]

        kedges = {}
        for i, files in enumerate(paths_k):
            kedges[str(names_k[i])[:-6]] = pd.read_csv(files, sep='\s+', skiprows=38, header=None)

        # Create subplots
        fig = make_subplots(rows=2, cols=2, vertical_spacing=0.1, horizontal_spacing=0.05)

        colors = ['rgb(31, 119, 180)', 'rgb(255, 127, 14)', 'rgb(44, 160, 44)', 'rgb(214, 39, 40)']

        # Plot each subplot
        for i, p in enumerate(kedges):
            data = kedges[p].loc[:, (0, 3)]
            data.columns = ['Wavenumber', 'X(k)']

            # Add trace to the subplot
            fig.add_trace(
                go.Scatter(
                    x=data['Wavenumber'],
                    y=data['X(k)'],
                    mode='lines',
                    name=labs[i],
                    line=dict(color=colors[i]),
                ),
                row=i // 2 + 1,
                col=i % 2 + 1,
            )
            fig.add_annotation(
                xref="paper",
                yref="paper",
                x=labs_xposi[i],
                y=labs_yposi[i],
                text=labs[i],
                font=dict(size=18),
                showarrow=False,
            )

        # Update axis labels and tick sizes
        fig.update_xaxes(title_text="Wavenumber", tickfont_size=18, title_font_size=20)
        fig.update_yaxes(title_text="X(k)", tickfont_size=18, title_font_size=20)
        fig.update_layout(height=(input.dimension()[1] - 180), showlegend=False)

        return fig

    @render_widget
    def rSpace():
        paths_R = [x for x in pl.Path('.').glob('Co_Data/*/*R*')]
        names_R = [x.stem for x in pl.Path('.').glob('Co_Data/*/*R*')]

        Rspace = {}
        for i, files in enumerate(paths_R):
            Rspace[str(names_R[i])[:-6]] = pd.read_csv(files, sep='\s+', skiprows=38, header=None)

        # Create subplots
        fig = make_subplots(rows=2, cols=2, vertical_spacing=0.1, horizontal_spacing=0.05)

        colors = ['red', 'blue']

        # Plot each subplot
        for i, p in enumerate(Rspace):
            data = Rspace[p].loc[:, (0, 1)]
            data.columns = ['Radial distance (Å)', '|X(R)| (A^(-3))']

            rdata = Rspace[p].loc[:, (0, 3)]
            rdata.columns = ['Radial distance (Å)', '|X(R)| (A^(-3))']

            # Add trace to the subplot for chi_R
            fig.add_trace(
                go.Scatter(
                    x=data['Radial distance (Å)'],
                    y=data['|X(R)| (A^(-3))'],
                    mode='lines',
                    name='chi_R',
                    line=dict(color=colors[0]),
                    showlegend=False,
                ),
                row=i // 2 + 1,
                col=i % 2 + 1,
            )

            # Add trace to the subplot for chir_mag
            fig.add_trace(
                go.Scatter(
                    x=rdata['Radial distance (Å)'],
                    y=rdata['|X(R)| (A^(-3))'],
                    mode='lines',
                    name='chir_mag',
                    line=dict(color=colors[1]),
                    showlegend=False,
                ),
                row=i // 2 + 1,
                col=i % 2 + 1,
            )
            # Add annotation
            fig.add_annotation(
                xref="paper",
                yref="paper",
                x=labs_xposi[i],
                y=labs_yposi[i],
                text=labs[i],
                font=dict(size=18),
                showarrow=False,
            )

        fig.update_xaxes(title_text="Radial distance (Å)", tickfont_size=18, title_font_size=20)
        fig.update_yaxes(title_text="|X(R)|(A<sup>-3</sup>)", tickfont_size=18, title_font_size=20)
        fig.update_layout(height=(input.dimension()[1] - 180))

        return fig

    def read_data(filename):
        original_data = pd.read_csv(filename, sep='\s+')

        x_Data = original_data['energy']
        y_Data = original_data['mutrans']
        # normalize y_Data with min-max normalization
        y_Data = (y_Data - np.min(y_Data)) / (np.max(y_Data) - np.min(y_Data))

        # verify the maximum value is 1
        y_Data.max()

        n = len(x_Data)  # original resolution
        return x_Data, y_Data, n

    @render_widget
    def plot_undersampled():
        filename = input.ex_filename()[0]['datapath']
        x_Data, y_Data, n = read_data(filename)
        print(x_Data.shape)
        print(y_Data.shape)
        print(f'Original Length: {n}')

        data = pd.DataFrame([x_Data, y_Data]).T

        # randomly undersample with set seed
        undersampling = input.undersampling_ex() / 100
        np.random.seed(0)  # seed
        ri = np.random.choice(n, int(n * (undersampling)), replace=False)
        ri.sort()
        print(f'Randomly sampled length with an Undersampling of {undersampling} is {len(ri)}')

        uSx = x_Data[ri].astype(int)  # undersampled X
        uSy = y_Data[ri]  # undersampled Y

        # prepare measurement Matrix B
        A = spfft.idct(np.identity(n), norm='ortho', axis=0)
        B = A[ri]

        # do L1 optimization
        vx = cvx.Variable(len(x_Data))
        objective = cvx.Minimize(cvx.norm(vx, 1))
        constraints = [B @ vx == uSy]
        prob = cvx.Problem(objective, constraints)
        result = prob.solve(solver='ECOS', verbose=True)

        # plot reconstructed signal
        x = np.array(vx.value)
        x = np.squeeze(x)
        sig = spfft.idct(x, norm='ortho', axis=0)
        fig = go.Figure()

        fig.add_trace(go.Scatter(x=x_Data, y=sig, mode='lines', name='Reconstructed Signal'))
        fig.add_trace(go.Scatter(x=x_Data, y=y_Data, mode='lines', name='Original Data'))

        fig.update_xaxes(title_text="Energy", tickfont_size=18, title_font_size=20)
        fig.update_yaxes(title_text="Mutrans", tickfont_size=18, title_font_size=20)
        fig.update_layout(height=(input.dimension()[1] - 180), legend_font_size=20,
                          legend_xanchor="right", legend_x=1, legend_bgcolor='rgba(0,0,0,0)')

        return fig

    @reactive.Effect
    @reactive.event(input.start_cs)
    def apply_cs():
        filename = input.meas_filename()[0]['datapath']
        x_Data, y_Data, n = read_data(filename)

        # preparation function
        def prepare_cs(n, undersampling, seed, x_Data, y_Data):
            np.random.seed(seed)
            ri = np.random.choice(n, int(n * (undersampling)), replace=False)
            ri.sort()
            A = spfft.idct(np.identity(n), norm='ortho', axis=0)
            uSx = x_Data[ri].astype(int)  # undersampled X
            uSy = y_Data[ri]  # undersampled Y
            B = A[ri]
            return B, uSy, uSx

        # wrapper to time the functions
        def timeit_wrapper(func, *args, **kwargs):
            from datetime import timedelta
            import time

            def wrap(*args, **kwargs):
                starttime = time.perf_counter()
                error = func(*args, **kwargs)
                duration = timedelta(seconds=time.perf_counter() - starttime)
                return duration, error

            return wrap

        # General function
        @timeit_wrapper
        def optimize(n, x_Data, y_Data, undersampling: float, solver, errors: [],
                     params: dict(), seed=None):
            B, uSy, uSx = prepare_cs(n, undersampling, seed, x_Data, y_Data)
            vx = cvx.Variable(n)
            objective = cvx.Minimize(cvx.norm(vx, 1))
            constraints = [B @ vx == uSy]
            prob = cvx.Problem(objective, constraints)
            result = prob.solve(solver=solver, verbose=False, **params)
            x = np.array(vx.value)
            x = np.squeeze(x)
            sig = spfft.idct(x, norm='ortho', axis=0)
            mse = ((y_Data - sig) ** 2).mean(axis=None)  # mean squared error
            errors.append(mse)

            # fig = go.Figure()
            # fig.add_trace(go.Scatter(x=x_Data, y=sig, mode='lines', name='Reconstructed Signal'))
            # fig.add_trace(go.Scatter(x=x_Data, y=y_Data, mode='lines', name='Original Signal', opacity=0.7))

            # # Update the layout to include title, axis labels, and text annotation
            # fig.update_layout(
            #     title=solver,
            #     xaxis=dict(title='Energy (eV)'),
            #     yaxis=dict(title='Absorption Coefficient (μ)'),
            #     legend=dict(font=dict(size=12)),
            #     annotations=[
            #         dict(
            #             x=7550,
            #             y=2.5,
            #             xref="x",
            #             yref="y",
            #             text="Error: {:.2e}".format(mse),
            #             showarrow=False,
            #             font=dict(size=12)
            #         )
            #     ]
            # )
            return mse

        # OMP
        @timeit_wrapper
        def optimize_OMP(n, undersampling: float, y_Data, solver, errors: [], params: dict(), seed=None):
            from sklearn.linear_model import OrthogonalMatchingPursuit
            import random
            B, uSy, uSx = prepare_cs(n, undersampling, seed=seed)
            # Define the original signal with 348 points
            original_signal_length = n
            original_signal = y_Data  # You can replace this with your actual signal

            # Define the undersampling rate (45% in this case)
            undersampling_rate = undersampling

            # Calculate the number of measurements
            num_measurements = int(original_signal_length * undersampling_rate)

            # Create the measurement matrix (DCT matrix)
            from scipy.fftpack import dct, idct
            dct_matrix = dct(np.identity(original_signal_length), norm='ortho')

            # Generate random indices for undersampling
            undersampled_indices = np.random.choice(original_signal_length, num_measurements, replace=False)

            # Create the undersampled signal
            undersampled_signal = original_signal[undersampled_indices]

            # Initialize the OMP model
            omp = OrthogonalMatchingPursuit(fit_intercept=False,
                                            **params)  # You can adjust the number of nonzero coefficients  n_nonzero_coefs=50,

            # Fit the OMP model to the undersampled signal
            omp.fit(dct_matrix[undersampled_indices, :], undersampled_signal)

            # Reconstruct the signal using the OMP coefficients
            reconstructed_signal = np.dot(dct_matrix, omp.coef_)

            # fig = go.Figure()
            # fig.add_trace(go.Scatter(x=list(range(len(original_signal))), y=original_signal, mode='lines', name='Original Signal'))
            # fig.add_trace(go.Scatter(x=list(range(len(reconstructed_signal))), y=reconstructed_signal, mode='lines', name='Reconstructed Signal'))

            # # Update the layout to include title and legend
            # fig.update_layout(
            #     title='Original vs. Reconstructed Signal',
            #     xaxis=dict(title='Index'),
            #     yaxis=dict(title='Signal Value'),
            #     legend=dict(font=dict(size=12))
            # )
            mse = ((y_Data - reconstructed_signal) ** 2).mean(axis=None)  # mean squared error
            errors.append(mse)
            return mse

        # LASSO
        @timeit_wrapper
        def optimize_LASSO(n, undersampling: float, y_Data, solver, errors: [], params: dict(), seed=None):
            from sklearn.linear_model import Lasso
            import random
            B, uSy, uSx = prepare_cs(n, undersampling, seed=seed)
            # Define the original signal with 348 points
            original_signal_length = n
            original_signal = y_Data  # Replace this with your actual signal

            # Define the undersampling rate (45% in this case)
            undersampling_rate = undersampling

            # Calculate the number of measurements
            num_measurements = int(original_signal_length * undersampling_rate)

            # Create the measurement matrix (DCT matrix)
            from scipy.fftpack import dct, idct
            dct_matrix = dct(np.identity(original_signal_length), norm='ortho')

            # Generate random indices for undersampling
            undersampled_indices = np.random.choice(original_signal_length, num_measurements, replace=False)

            # Create the undersampled signal
            undersampled_signal = original_signal[undersampled_indices]

            # Initialize the LASSO model
            lasso = Lasso(alpha=0.00005, fit_intercept=False,
                          **params)  # You can adjust the regularization strength (alpha)

            # Fit the LASSO model to the undersampled signal
            lasso.fit(dct_matrix[undersampled_indices, :], undersampled_signal)

            # Reconstruct the signal using LASSO coefficients
            reconstructed_signal = lasso.coef_.dot(dct_matrix.T)

            # fig = go.Figure()
            # fig.add_trace(go.Scatter(x=list(range(len(original_signal))), y=original_signal, mode='lines', name='Original Signal'))
            # fig.add_trace(go.Scatter(x=list(range(len(reconstructed_signal))), y=reconstructed_signal, mode='lines', name='Reconstructed Signal'))

            # fig.update_layout(
            #     title='Original vs. Reconstructed Signal (LASSO)',
            #     xaxis=dict(title='Index'),
            #     yaxis=dict(title='Signal Value'),
            #     legend=dict(font=dict(size=12))
            # )
            mse = ((y_Data - reconstructed_signal) ** 2).mean(axis=None)  # mean squared error
            errors.append(mse)
            return mse

        repetitions = input.rep()
        with ui.Progress(min=0, max=repetitions) as p:
            p.set(message="Calculation in progress")

            undersampling = input.undersampling_comp() / 100
            solvers = ['ECOS', 'SCS', 'OSQP']  # 'MOSEK'
            # give a list of 200 random numbers between 0 and 1000 using np.random
            np.random.seed(0)
            seeds = np.random.choice(2 * repetitions, repetitions, replace=False)
            results = dict()
            for solver in solvers:
                results[solver] = dict()
                results[solver]['Error'] = []
                results[solver]['Time'] = []

            for j, repetition in enumerate(range(repetitions)):
                p.set(j, message="Applying CS", detail=f"{repetition} of {repetitions}")

                for solver in solvers:
                    time_used, error = optimize(n, x_Data, y_Data, undersampling, solver, [], {},
                                                seed=seeds[repetition])
                    results[solver]['Time'].append(time_used)
                    results[solver]['Error'].append(error)

            # Store results in a pickle file
            with open(os.path.join(output_dir, 'error_comparison.pkl'), 'wb') as f:
                pickle.dump(results, f)

    @render_widget
    def compareSolvers():
        with open(os.path.join(output_dir, 'error_comparison.pkl'), 'rb') as f:
            results = pickle.load(f)

        fig = go.Figure()

        for label, solver_data in results.items():
            fig.add_trace(go.Box(y=solver_data['Error'], name=label))

        fig.update_layout(
            xaxis_title='Model',
            yaxis_title='Error Value',
            height=(input.dimension()[1] - 180),
        )
        return fig


app = App(app_ui, server)
