"""Core library for stream membership likelihood, with ML."""

from __future__ import annotations

__all__: tuple[str, ...] = ()

from functools import wraps
from typing import TYPE_CHECKING, Any, ParamSpec, TypeVar, cast

import matplotlib as mpl
import numpy as np
from matplotlib import gridspec
from matplotlib import pyplot as plt

from stream_mapper.core import WEIGHT_NAME
from stream_mapper.core.setup_package import BACKGROUND_KEY
from stream_mapper.visualization._defaults import LABEL_DEFAULTS
from stream_mapper.visualization._utils.arg_decorators import make_tuple
from stream_mapper.visualization._utils.plt_decorators import (
    add_savefig_option,
    with_tight_layout,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from matplotlib.axes import Axes
    from matplotlib.figure import Figure

    from stream_mapper.core import Data, Model, Params
    from stream_mapper.core.typing import Array

    P = ParamSpec("P")
    R = TypeVar("R")


def _with_ax_panels(plotting_func: Callable[P, R]) -> Callable[P, R]:
    @wraps(plotting_func)
    def with_ax_panels_inner(*args: P.args, **kwargs: P.kwargs) -> R:
        if "ax" in kwargs and "ax_top" in kwargs:
            pass

        elif "fig" in kwargs and "gs" in kwargs:
            coord: str = cast("str", kwargs["coord"])
            fig: plt.Figure = kwargs.pop("fig")
            gs: gridspec.GridSpec = kwargs.pop("gs")

            gsi = gs.subgridspec(2, 1, height_ratios=(1, 3))

            # Axes
            ax = fig.add_subplot(gsi[1])
            ax.set_xlabel(r"$\phi_1$")
            ax.set_ylabel(LABEL_DEFAULTS.get(coord, coord))

            # Plot Weight histogram
            ax_top = fig.add_subplot(gsi[0], sharex=ax)
            ax_top.tick_params(axis="x", labelbottom=False)
            ax_top.set_ylabel(r"weight")

            kwargs["ax"] = ax
            kwargs["ax_top"] = ax_top

        else:
            msg = "Must provide either `ax` and `ax_top` or `fig` and `gs`."
            raise KeyError(msg)

        # Call the plotting function.
        return plotting_func(*args, **kwargs)

    return with_ax_panels_inner


# --------------------------------------------------


@_with_ax_panels
def _plot_coordinate_component(  # noqa: PLR0913
    model: Model[Array],
    /,
    data: Data[Array],
    mpars: Params[Array],
    *,
    component: str,
    coord: str,
    log_weight: bool = False,
    where: Array | None = None,
    ax: Axes,
    ax_top: Axes | None,
    y: str = "mu",
    y_err: str = "ln-sigma",
) -> Axes:
    """Plot a single coordinate for a single component.

    Parameters
    ----------
    model : Model[Array]
        The model to plot.
    data : Data[Array]
        The data to plot.
    mpars : Params
        The parameters to plot.
    component : str, keyword-only
        The component to plot.
    coord : str, keyword-only
        The coordinate to plot.

    log_weight : bool, keyword-only
        Whether to plot the log of the weights.
    where : Array | None, keyword-only
        The indices to plot.

    ax : Axes, keyword-only
        The axes to plot on.
    ax_top : Axes | None, keyword-only
        The axes to plot the weights on.
    y : str, keyword-only
        The name of the mean parameter.
    y_err : str, keyword-only
        The name of the log-standard deviation parameter.

    Returns
    -------
    Axes
        The axes that were plotted on.
    """
    ps = mpars.get_prefixed(component)

    phi1 = data["phi1"].flatten()
    mu = ps[coord, y].flatten()
    yerr = np.exp(ps[coord, y_err].flatten())

    im = ax.plot(phi1[where], mu[where], label=f"{component}", lw=1)
    fc = im[0].get_color()

    ax.fill_between(
        phi1,
        y1=mu + 2 * yerr,
        y2=mu - 2 * yerr,
        facecolor=fc,
        alpha=0.25,
        where=where,
    )
    ax.fill_between(
        phi1,
        y1=mu + yerr,
        y2=mu - yerr,
        facecolor=fc,
        alpha=0.5,
        where=where,
    )

    if ax_top is not None and "weight" in ps:
        ax_top.plot(
            phi1,
            np.log(ps[("weight",)]) if log_weight else ps[("weight",)],
            label=f"{component}[weight]",
        )

    return ax


# --------------------------------------------------


@_with_ax_panels
def _plot_coordinate_panel(  # noqa: PLR0913
    model: Model[Array],
    /,
    data: Data[Array],
    mpars: Params[Array],
    *,
    indep_coord: str,
    coord: str,
    components: tuple[str, ...],
    coord2par: dict[str, str],
    ax: Axes,
    ax_top: Axes,
    log_weight: bool = False,
    min_weight: float = 1e-4,
    **kwargs: Any,
) -> tuple[Axes, Axes]:
    """Plot a single coordinate for all components."""
    # --- plot data ---

    if kwargs.get("use_hist", False):
        func = ax.hist2d
        pkw = {
            "bins": kwargs.get("bins", 100),
            "cmap": "Greys",
            "norm": mpl.colors.LogNorm(),
        }
    else:
        func = ax.plot
        pkw = {"c": "black", "marker": ",", "linestyle": "none"}

    func(data[indep_coord].flatten(), data[coord].flatten(), **pkw)

    # --- plot components ---

    # Skip the background component, plotting it first
    if BACKGROUND_KEY in components:
        i = components.index(BACKGROUND_KEY)
        components = components[:i] + components[i + 1 :]
        has_background = True
    else:
        has_background = False

    # Include background in top plot, if applicable
    if has_background:
        background_weight = (f"{BACKGROUND_KEY}.{WEIGHT_NAME}",)
        ax_top.plot(
            data[indep_coord].flatten(),
            np.log(mpars[background_weight].flatten())
            if log_weight
            else mpars[background_weight].flatten(),
            color="black",
            label="background[weight]",
        )

    for comp in components:
        weight = mpars.get(f"{comp}.{WEIGHT_NAME}")

        _plot_coordinate_component(
            model,
            data,
            mpars,
            component=comp,
            coord=coord2par.get(coord, coord),
            log_weight=log_weight,
            where=(weight >= min_weight) if weight is not None else None,
            ax=ax,
            ax_top=ax_top,
            y="mu",
            y_err="ln-sigma",
        )

    # Bottom plot
    ax.set_ylim(data[coord].min(), data[coord].max())
    ax.legend(fontsize=kwargs.get("legend_fontsize", plt.rcParams["font.size"]))

    # top plot
    if "weight" in mpars:
        ax_top.legend(
            fontsize=kwargs.get("top_legend_fontsize", plt.rcParams["font.size"])
        )
    ax_top.set_yscale(kwargs.get("top_yscale", "linear"))

    return ax, ax_top


# --------------------------------------------------


@add_savefig_option
@with_tight_layout
@make_tuple("components", "coords")
def astrometric_model_panels(  # noqa: PLR0913
    model: Model[Array],
    /,
    data: Data[Array],
    mpars: Params[Array],
    *,
    components: tuple[str, ...] = ("stream",),
    coords: tuple[str, ...] = ("phi2",),
    coord2par: dict[str, str] | None = None,
    **kwargs: Any,
) -> Figure:
    r"""Diagnostic plot of the model.

    Parameters
    ----------
    model : Model, positional-only
        The model to plot.

    data : Data
        The data to plot. Must be sorted by :math:`\phi_1`.
    mpars : Params[Array]
        The prediction to plot.

    components : tuple[str, ...], keyword-only
        The component(s) to plot.
    coords : tuple[str, ...], keyword-only
        The coordinate(s) to plot.
    coord2par : dict[str, str], optional
        A mapping from coordinate to parameter name. Defaults to the identity
        mapping.
    **kwargs : Any
        Additional keyword arguments.

        - figsize : tuple[float, float], optional
           Uses ``plt.rcParams["figure.figsize"]`` by default.
        - legend_fontsize : float, optional
           Uses ``plt.rcParams["legend.fontsize"]`` by default.
        - top_legend_fontsize : float, optional
           Uses ``plt.rcParams["legend.fontsize"]`` by default.
        - top_yscale : str, optional
           Uses ``"linear"`` by default.
        - use_hist : bool, optional
            Whether to use a histogram for the data. `False` by default.
        - log_weight : bool, optional
            Whether to plot the log of the weights. `False` by default.
        - min_weight : float, optional
            The minimum weight to plot. `1e-4` by default.

    Returns
    -------
    Figure
        The figure that was plotted.
    """
    if "coord" in kwargs:
        msg = "Use `coords` instead of `coord`."
        raise ValueError(msg)

    # Now figure out how many rows and columns we need
    figsize = kwargs.pop("figsize", plt.rcParams["figure.figsize"])
    fig = plt.figure(constrained_layout=True, figsize=figsize)

    # TODO! option to divide into multiple rows
    gs = gridspec.GridSpec(1, len(coords), figure=fig)  # main GridSpec

    for i, cn in enumerate(coords):
        _ = _plot_coordinate_panel(
            model,
            fig=fig,
            gs=gs[i],
            indep_coord="phi1",
            coord=cn,
            data=data,
            mpars=mpars,
            components=components,
            coord2par=coord2par if coord2par is not None else {},
            **kwargs,
        )

    return fig
