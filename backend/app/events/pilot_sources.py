"""Explicit pilot registry; not imported by shared HTTP event routes."""
from .pilot_catalog import PILOT_PROJECT
from .pilot_pordenonelegge import collect_pordenonelegge
from .pilot_cinema_muto import collect_cinema_muto
from .pilot_regional_verified import collect_regional_verified
from .pilot_azalea import collect_azalea
from .pilot_css import collect_css
from .pilot_pnpensa import collect_pnpensa
from .pilot_verdi_pordenone import collect_verdi_pordenone
from .pilot_verdi_trieste import collect_verdi_trieste
from .pilot_paesiinfesta import collect_paesiinfesta
from .pilot_sagrefvg import collect_sagrefvg
from .pilot_villa_manin import collect_villa_manin
from .pilot_magazzino import collect_magazzino
from .pilot_mess import collect_mess
from .pilot_spazzapan import collect_spazzapan
from .pilot_barcolana import collect_barcolana


def source_adapters(project):
    if project != PILOT_PROJECT:
        raise ValueError("isolated pilot project required")
    return {"TurismoFVG": collect_regional_verified, "Pordenonelegge": collect_pordenonelegge,
            "Le Giornate del Cinema Muto": collect_cinema_muto,
            "Azalea": collect_azalea, "CSS Udine": collect_css,
            "Pordenone Pensa": collect_pnpensa,
            "Teatro Verdi Pordenone": collect_verdi_pordenone,
            "Teatro Verdi Trieste": collect_verdi_trieste,
            "Paesi in Festa": collect_paesiinfesta,
            "SagreFVG": collect_sagrefvg,
            "Villa Manin": collect_villa_manin,
            "Magazzino delle Idee": collect_magazzino,
            "MESS": collect_mess,
            "Galleria Spazzapan": collect_spazzapan,
            "Barcolana": collect_barcolana}
