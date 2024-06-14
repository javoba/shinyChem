from shinywidgets import output_widget, render_widget
from shiny import App, ui, reactive

import numpy as np
import math
import scipy as sp
import plotly.graph_objs as go
from plotly.subplots import make_subplots
import sympy

# Global constants
global mu0, eps0
mu0 = 4e-7 * np.pi
eps0 = 8.854e-12

# Initialize the physical parameters of the HTC
a = 15 / 1000  # Inner diameter of the cylinder in meters
b = 30 / 1000  # Outer diameter of the cylinder in meters
h = 10 / 1000  # Height of the cylinder in meters

# Initialize the electrical parameters of the inductor
N = 50  # Number of windings
R = 100  # Resistance in Ohm
d = 0.0007  # Diameter of the wire in meters
rho = 1.72e-8  # Resistivity of the wire (for copper)


def generate_sys(a, b, h, d, N, R):
    """
    Generates transfer function of a system based on physical parameters.

    Parameters
    ----------
    a : float
        Inner diameter of the cylinder in meters.
    b : float
        Outer diameter of the cylinder in meters.
    h : float
        Height of the cylinder in meters.
    N : int
        Number of windings.
    R : float
        Resistance of the wire in Ohm.

    Returns
    -------
    sys : TransferFunction
        Transfer function of the system.

    """
    # Calculate all neccessary parameters
    wl = ((b-a) + 2*h)*N + b*np.pi  # wire length
    M = mu0*N*h / (2*np.pi) * np.log(b/a)  # mutual inductance

    L = N * M  # self inductance
    C = 4*np.pi**2*eps0*(b + a) / (np.log10((b+a) / (b-a)))  # capacitance
    r = rho*4*wl / (np.pi*d**2)  # Resistance of the wire

    t, s = sympy.symbols('t, s')  # for laplace transform

    H = M*s / (L*C*s**2 + (L/R + r*C)*s + (R+r)/R)  # transfer function
    F = sympy.laplace_transform(H, t, s, noconds=True)  # perform laplace transform

    # Create system from transformed transfer function
    up = F.args[0]
    num = [-float(up), 0]
    down = F.args[1].args[0].args
    den = np.zeros(3)
    for d_i in down:

        if str(d_i).endswith("*s**2"):
            den[0] = float(str(d_i).replace("*s**2", ""))
        elif str(d_i).endswith("*s"):
            den[1] = float(str(d_i).replace("*s", ""))
        else:
            den[2] = float(d_i)

    """
    # alternative (easier) way to create system, but hacky 
    num = [-M, 0]
    den = [L*C, L/R + r*C, (R+r)/R]
    """
    sys = sp.signal.TransferFunction(num, den)
    return sys


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
            ui.input_slider("b", "Outer Diameter", 16, 50, 30, post="mm"),
            ui.input_slider("h", "Height", 1, 50, 15, post="mm"),
            ui.input_slider("N", "Coil Windings", 1, 100, 50),
            ui.input_slider("R", "Terminating Resistance", -1, 4, 1, step=0.1, pre="10^", post="Ω"),
            width="300px",
        ),
        ui.h1("Bode Plot"),
        output_widget("plot_bode"),
    ),
    title="Bode Plot"
)


def server(input, output, session):

    @reactive.effect
    @reactive.event(input.a)
    def _():
        # Update the label of the pet name input
        ui.update_slider("b", min=input.a()+1)

    @render_widget
    def plot_bode():
        a = input.a() / 1000
        b = input.b() / 1000
        h = input.h() / 1000
        N = int(input.N())
        R = 10 ** input.R()

        sys = generate_sys(a, b, h, d, N, R)
        om_list = np.logspace(0, 15, 500)  # frequency range to plot (in Hz)
        omega, mag, phase = sp.signal.bode(sys, w=om_list)
        omega = [w/1e6 for w in omega]  # convert frequency to MHz

        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.05)

        fig.add_trace(go.Scatter(x=omega, y=mag, mode='lines', name='Magnitude', line=dict(color='blue')), row=1, col=1)
        fig.add_trace(go.Scatter(x=omega, y=phase+180, mode='lines', name='Phase', line=dict(color='blue')), row=2, col=1)

        xticklabels = [10 ** i for i in range(-6, 9, 2)]
        # Define the corresponding tick labels
        x_ticktext = [f"10<sup>{i}</sup>" for i in range(-6, 9, 2)]

        # Update the axes properties for both subplots
        fig.update_xaxes(type="log", tickvals=xticklabels, ticktext=x_ticktext, tickfont=dict(size=18), title_font=dict(size=20))
        fig.update_xaxes(title_text="Frequency [MHz]", row=2, col=1)
        fig.update_yaxes(title_text="Magnitude [dB]", tickfont=dict(size=18), title_font=dict(size=20), row=1, col=1)
        fig.update_yaxes(range=[-100, 100], title_text="Phase [°]", tickfont=dict(size=18), title_font=dict(size=20), row=2, col=1)

        # Update layout
        fig.update_layout(showlegend=False, height=input.dimension()[1]-180)
        return fig


app = App(app_ui, server)
