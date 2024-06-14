from shiny import App, ui, reactive
from shinywidgets import output_widget, render_widget

import numpy as np
import math
import scipy as sp
import plotly.express as px
import plotly.graph_objs as go
from plotly.subplots import make_subplots

# Global constants
mu0 = 4e-7 * np.pi
eps0 = 8.854e-12

d = 0.0005  # Diameter of the wire in meters
rho = 1.72e-8  # Resistivity of the wire (for copper)

extension = 3


def generate_sys(a, b, h, d, N, R):
    # Calculate all necessary parameters
    wl = ((b - a) + 2 * h) * N + b * np.pi  # wire length
    M = mu0 * N * h / (2 * np.pi) * math.log(b / a)  # mutual inductance

    L = N * M  # self inductance
    C = 4 * np.pi ** 2 * eps0 * (b + a) / (math.log10((b + a) / (b - a)))  # capacitance
    r = rho * 4 * wl / (np.pi * d ** 2)  # Resistance of the wire

    # Calculate the transfer function
    num = [M, 0]
    den = [L * C, L / R + r * C, (R + r) / R]

    sys = sp.signal.TransferFunction(num, den)
    return sys, L


def fourierana(signal, sample_rate):
    """
    Computes the Fourier Transform (FT) of a given signal.

    Args:
        signal (numpy.ndarray): The input signal to transform.
        sample_rate (int): The sample rate (in Hz) at which the signal was recorded.

    Returns:
        tuple: A tuple of three numpy arrays representing the magnitude, phase, and frequency components of the FT.
    """
    # Apply Hanning window to signal
    window = np.hanning(len(signal))
    signal_windowed = signal * window

    # Pad the windowed signal with zeros
    padding = np.zeros(len(signal_windowed))
    signal_padded = np.concatenate((signal_windowed, padding))

    # Perform FT of windowed signal
    ft_signal = sp.fft.fft(signal_padded, len(signal))
    ft_magnitude = np.abs(ft_signal)
    ft_phase = np.rad2deg(np.angle(ft_signal))

    # Compute frequency axis of FT
    ft_freq = np.fft.fftfreq(signal.shape[-1], 1 / sample_rate)

    # only use positive frequencies
    positive_freq_mask = ft_freq >= 0
    ft_magnitude = ft_magnitude[positive_freq_mask]
    ft_phase = ft_phase[positive_freq_mask]
    ft_freq = ft_freq[positive_freq_mask]

    return ft_magnitude, ft_phase, ft_freq


def double_sigmoidal(t, A, w, xc, r):
    """
    Computes a double sigmoidal function.

    Parameters:
        t (array): Time values.
        A (float): Amplitude of the function.
        w (float): Width of the function.
        xc (float): Center of the function.
        r (float): Parameter controlling the slope.

    Returns:
        array: The computed double sigmoidal function.
    """
    # Input function parameters
    y0 = 0  # Vertical offset (not needed here)
    w1 = 1 / w / r  # Rising slope
    w2 = 1 / w * r  # Falling slope
    return y0 + A * 1 / (1 + np.exp(-(t - xc) / w1)) * (1 - 1 / (1 + np.exp(-(t - xc) / w2)))


def extend_data(t_full, t, A):
    """
    Extend time and amplitude data to include the points before and after reconstruction.

    Args:
        t_full (array): Array of original time values.
        t (array): Array of interpolated time values.
        A (array): Amplitude values.

    Returns:
        t_ext (array): Extended time values.
        A_ext (array): Extended amplitude values.
    """
    # Generate time values before the reconstruction starts
    t_before = np.arange(min(t_full), min(t), t[1] - t[0])
    # Generate time values after the reconstruction ends
    t_after = np.arange(max(t), max(t_full), t[1] - t[0])
    # Concatenate the time values to create an extended time array
    t_ext = np.concatenate((t_before, t, t_after))

    # Create arrays of zeros with the same shape as t_before and t_after
    A_before = np.zeros_like(t_before)
    A_after = np.zeros_like(t_after)
    # Concatenate the reconstructed amplitudes to create an extended amplitude array
    A_ext = np.concatenate((A_before, A, A_after))

    return t_ext, A_ext


def calcfourier(t, y, extension):
    """
    Plots the Fourier Transform magnitude and phase of a signal.

    Parameters:
        sfig (matplotlib.axes.Axes): The subplot where the Fourier Transform magnitude will be plotted.
        axphi (matplotlib.axes.Axes): The subplot where the Fourier Transform phase will be plotted.
        y (array-like): The input signal.
        t (array-like): The time values corresponding to the input signal.

    Returns:
        None
    """
    t_min = min(t) / extension  # Define minimum time value of extended signal
    t_max = max(t) * extension  # Define maximum time value of extended signal

    if extension > 1:
        t_ext = np.linspace(t_min, t_max, int((t_max - t_min) // 2e-9))  # Create extended time array
        t_ext, y_ext = extend_data(t_ext, t, y)  # Extend the data
    else:
        t_ext = t
        y_ext = y

    sample_rate = len(t_ext) / (t_ext[-1] - t_ext[0])  # Calculate the sample rate
    ft_magnitude, ft_phase, ft_freq = fourierana(y_ext, sample_rate)  # calculate Fourier spectrum
    return ft_magnitude, ft_freq


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
            ui.h3("HTC Parameters"),
            ui.input_slider("a", "Inner Diameter", 5, 40, 10, post="mm"),
            ui.input_slider("b", "Outer Diameter", 11, 50, 30, post="mm"),
            ui.input_slider("h", "Height", 1, 50, 15, post="mm"),
            ui.input_slider("N", "Coil Windings", 1, 100, 50),
            ui.input_slider("R", "Terminating Resistance", -1, 4, 1, step=0.1, pre="10^", post="Ω"),
            width="300px",
        ),
        # ui.h1("Pulse Response", style='text-align: center'),
        ui.row(
            ui.column(5,
                      ui.h4("Input Signal", style='text-align: center'),
                      output_widget("plot_input")
                      ),
            ui.column(2,
                      ui.card(
                          ui.card_header("Main Pulse"),
                          ui.row(
                              ui.column(3, ui.p("A")),
                              ui.column(9, ui.input_slider("A1", "", -1, 1, 1, step=0.01, post="V"), ),
                          ),
                          ui.row(
                              ui.column(3, ui.p("w")),
                              ui.column(9, ui.input_slider("w1", "", 4, 8, 6, step=0.01, pre="10^", post="Hz")),
                          ),
                          ui.row(
                              ui.column(3, ui.p("dt")),
                              ui.column(9, ui.input_slider("mu1", "", 0, 100, 10, step=0.01, post="%")),
                          ),
                          ui.row(
                              ui.column(3, ui.p("r")),
                              ui.column(9, ui.input_slider("r1", "", -1, 1, 0, step=0.01)),
                          ),
                      ),
                      ui.card(
                          ui.card_header("Secondary Pulse 1"),
                          ui.row(
                              ui.column(3, ui.p("A")),
                              ui.column(9, ui.input_slider("A2", "", -1, 1, 0, step=0.01, post="V")),
                              gap="100px"
                          ),
                          ui.row(
                              ui.column(3, ui.p("w")),
                              ui.column(9, ui.input_slider("w2", "", 5, 7, 6, step=0.01, pre="10^", post="Hz")),
                          ),
                          ui.row(
                              ui.column(3, ui.p("dt")),
                              ui.column(9, ui.input_slider("mu2", "", 0, 100, 10, step=0.01, post="%")),
                          ),
                          ui.row(
                              ui.column(3, ui.p("r")),
                              ui.column(9, ui.input_slider("r2", "", -1, 1, 0, step=0.01)),
                          ),
                      ),
                      ui.card(
                          ui.card_header("Secondary Pulse 2"),
                          ui.row(
                              ui.column(3, ui.p("A")),
                              ui.column(9, ui.input_slider("A3", "", -1, 1, 0, step=0.01, post="V")),
                          ),
                          ui.row(
                              ui.column(3, ui.p("w")),
                              ui.column(9, ui.input_slider("w3", "", 3, 9, 6, step=0.01, pre="10^", post="Hz")),
                          ),
                          ui.row(
                              ui.column(3, ui.p("dt")),
                              ui.column(9, ui.input_slider("mu3", "", 0, 100, 10, step=0.01, post="%")),
                          ),
                          ui.row(
                              ui.column(3, ui.p("r")),
                              ui.column(9, ui.input_slider("r3", "", -1, 1, 0, step=0.01)),
                          ),
                      ),
                      ),
            ui.column(5,
                      ui.h4("Response Signal", style='text-align: center'),
                      output_widget("plot_output"),
                      ),
        ),
    ),
    title="Pulse Response"
)


def server(input, output, session):
    def read_HTC():
        a = input.a() / 1000
        b = input.b() / 1000
        h = input.h() / 1000
        N = int(input.N())
        R = 10 ** input.R()
        return a, b, h, N, R

    def read_signal():
        A1 = input.A1()
        w1 = 10 ** input.w1()
        mu1 = input.mu1() / w1
        r1 = 10 ** input.r1()

        A2 = input.A2()
        w2 = 10 ** input.w2()
        mu2 = input.mu2() / w1
        r2 = 10 ** input.r2()

        A3 = input.A3()
        w3 = 10 ** input.w3()
        mu3 = input.mu3() / w1
        r3 = 10 ** input.r3()

        # Generate input signal
        t = np.linspace(0, 100 / w1, 1000)  # time array
        y_s = A1 * double_sigmoidal(t, 4, w1, mu1, r1) + A2 * double_sigmoidal(t, 4, w2, mu2,
                                                                               r2) + A3 * double_sigmoidal(t, 4, w3,
                                                                                                           mu3, r3)
        return t, y_s

    @reactive.effect
    @reactive.event(input.a)
    def _():
        # Update the label of the pet name input
        ui.update_slider("b", min=input.a() + 1)

    @reactive.effect
    @reactive.event(input.w1)
    def _():
        w1 = input.w1()
        ui.update_slider("w2", min=w1 - 1, max=w1 + 1)
        ui.update_slider("w3", min=w1 - 1, max=w1 + 1)

    @render_widget
    def plot_input():
        t, y_s = read_signal()
        ft_mag, ft_freq = calcfourier(t, y_s, extension)
        freqmax = int(128 * extension / 2)

        fig = make_subplots(rows=2, cols=1, vertical_spacing=0.1)

        fig.add_trace(go.Scatter(x=t, y=y_s, mode='lines', line=dict(color='blue')), row=1, col=1)
        fig.add_trace(go.Scatter(x=ft_freq[:freqmax] / 1e6, y=ft_mag[:freqmax], mode='lines', line=dict(color='blue')),
                      row=2, col=1)

        # Update the axes properties for both subplots
        fig.update_xaxes(title_text="Time [s]", tickfont=dict(size=18), title_font=dict(size=20), row=1, col=1)
        fig.update_xaxes(title_text="Frequency [MHz]", tickfont=dict(size=18), title_font=dict(size=20), row=2, col=1)
        fig.update_yaxes(title_text="Magnitude [V]", tickfont=dict(size=18), title_font=dict(size=20))
        fig.update_yaxes(range=[0, max(ft_mag[:freqmax]) * 1.05], row=2, col=1)

        # Update layout
        fig.update_layout(showlegend=False, height=input.dimension()[1] - 115)
        # fig.update_xaxes(type="log")

        return fig

    @render_widget
    def plot_output():
        a, b, h, N, R = read_HTC()
        t, y_s = read_signal()

        sys, L = generate_sys(a, b, h, d, N, R)  # transfer function

        freqmax = int(128 * extension / 2)

        # Calculate the response of the system
        tout, y_r, x = sp.signal.lsim(sys, y_s, t)

        ft_mag_r, ft_freq_r = calcfourier(tout, y_r, extension)
        fig = make_subplots(rows=2, cols=1, vertical_spacing=0.1)

        fig.add_trace(go.Scatter(x=tout, y=y_r, mode='lines', line=dict(color='orange')), row=1, col=1)
        fig.add_trace(
            go.Scatter(x=ft_freq_r[:freqmax] / 1e6, y=ft_mag_r[:freqmax], mode='lines', line=dict(color='orange')),
            row=2, col=1)

        # Update the axes properties for both subplots
        fig.update_xaxes(title_text="Time [s]", tickfont=dict(size=18), title_font=dict(size=20), row=1, col=1)
        fig.update_xaxes(title_text="Frequency [MHz]", tickfont=dict(size=18), title_font=dict(size=20), row=2, col=1)
        fig.update_yaxes(title_text="Magnitude [V]", tickfont=dict(size=18), title_font=dict(size=20))
        fig.update_yaxes(range=[0, max(ft_mag_r[:freqmax]) * 1.05], row=2, col=1)

        fig.update_layout(showlegend=False, height=input.dimension()[1] - 115)
        return fig


app = App(app_ui, server)
