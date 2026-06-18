from __future__ import annotations


SIGNAL_LABELS = {
    "c_amb_h2": ("Ambient H2 concentration", "ppm"),
    "c_amb_o2": ("Ambient O2 concentration", "%"),
    "c_h2ino2": ("H2 in O2 concentration", "ppm"),
    "c_o2inh2": ("O2 in H2 concentration", "ppm"),
    "cond_an_in": ("Anode inlet conductivity", "µS/cm"),
    "cond_an_out": ("Anode outlet conductivity", "µS/cm"),
    "cond_an_sepr": ("Anode separator conductivity", "µS/cm"),
    "cond_cat_in": ("Cathode inlet conductivity", "µS/cm"),
    "cond_cat_out": ("Cathode outlet conductivity", "µS/cm"),
    "cond_cat_sepr": ("Cathode separator conductivity", "µS/cm"),
    "i_psu_set": ("Power supply current setpoint", "A"),
    "i_second": ("Secondary current", "A"),
    "i_set": ("Current setpoint", "A"),
    "mf_an_in": ("Anode inlet mass flow", "kg/h"),
    "mf_an_in_set": ("Anode inlet mass flow setpoint", "kg/h"),
    "mf_cat_in": ("Cathode inlet mass flow", "kg/h"),
    "mf_cat_in_set": ("Cathode inlet mass flow setpoint", "kg/h"),
    "mf_h2": ("H2 mass flow", "Nm³/h"),
    "mf_h2_raw": ("Raw H2 mass flow", "Nm³/h"),
    "mf_o2": ("O2 mass flow", "Nm³/h"),
    "mf_o2_raw": ("Raw O2 mass flow", "Nm³/h"),
    "p_an_ctrlmode": ("Anode pressure control mode", "-"),
    "p_an_in": ("Anode inlet pressure", "barg"),
    "p_an_in_set": ("Anode inlet pressure setpoint", "barg"),
    "p_an_out": ("Anode outlet pressure", "barg"),
    "p_an_out_set": ("Anode outlet pressure setpoint", "barg"),
    "p_an_set": ("Anode pressure setpoint", "barg"),
    "p_cat_ctrlmode": ("Cathode pressure control mode", "-"),
    "p_cat_in": ("Cathode inlet pressure", "barg"),
    "p_cat_in_set": ("Cathode inlet pressure setpoint", "barg"),
    "p_cat_out": ("Cathode outlet pressure", "barg"),
    "p_cat_out_set": ("Cathode outlet pressure setpoint", "barg"),
    "p_cat_sepr": ("Cathode separator pressure", "barg"),
    "p_cat_sepr_set": ("Cathode separator pressure setpoint", "barg"),
    "p_cat_set": ("Cathode pressure setpoint", "barg"),
    "t_amb": ("Ambient temperature", "°C"),
    "t_an_avg": ("Average anode temperature", "°C"),
    "t_an_cooler_out": ("Anode cooler outlet temperature", "°C"),
    "t_an_ctrlmode": ("Anode temperature control mode", "-"),
    "t_an_diff": ("Anode temperature difference", "°C"),
    "t_an_in": ("Anode inlet temperature", "°C"),
    "t_an_in_second": ("Secondary anode inlet temperature", "°C"),
    "t_an_in_set": ("Anode inlet temperature setpoint", "°C"),
    "t_an_out": ("Anode outlet temperature", "°C"),
    "t_an_out_set": ("Anode outlet temperature setpoint", "°C"),
    "t_an_pump_out": ("Anode pump outlet temperature", "°C"),
    "t_an_set": ("Anode temperature setpoint", "°C"),
    "t_cat_avg": ("Average cathode temperature", "°C"),
    "t_cat_ctrlmode": ("Cathode temperature control mode", "-"),
    "t_cat_diff": ("Cathode temperature difference", "°C"),
    "t_cat_in": ("Cathode inlet temperature", "°C"),
    "t_cat_in_set": ("Cathode inlet temperature setpoint", "°C"),
    "t_cat_out": ("Cathode outlet temperature", "°C"),
    "t_cat_out_second": ("Secondary cathode outlet temperature", "°C"),
    "t_cat_out_set": ("Cathode outlet temperature setpoint", "°C"),
    "t_cat_sepr_in": ("Cathode separator inlet temperature", "°C"),
    "t_cat_set": ("Cathode temperature setpoint", "°C"),
    "time_stamp": ("Timestamp", "-"),
    "u_psu_set": ("Power supply voltage setpoint", "V"),
    "u_set": ("Voltage setpoint", "V"),
    "vf_an_in": ("Anode inlet volumetric flow", "l/h"),
    "vf_an_in_second": ("Secondary anode inlet volumetric flow", "l/h"),
    "vf_an_in_set": ("Anode inlet volumetric flow setpoint", "l/h"),
    "vf_an_out": ("Anode outlet volumetric flow", "l/h"),
    "vf_cat_in": ("Cathode inlet volumetric flow", "l/h"),
    "vf_cat_in_set": ("Cathode inlet volumetric flow setpoint", "l/h"),
    "u_cell_map": ("Cell voltage map", "V"),
    "lowprio_map": ("Low-priority map", "-"),
    "calc": ("Calculated values", "-"),
    "i": ("Current", "A"),
    "u": ("Voltage", "V"),
    "j": ("Current density", "A/cm²"),
    "j_set": ("Current density setpoint", "A/cm²"),
    "u_cell_avg": ("Average cell voltage", "V"),
}


def get_signal_label(signal_name: str) -> str:
    label, _unit = SIGNAL_LABELS.get(signal_name, (signal_name, ""))
    return label


def get_signal_unit(signal_name: str) -> str:
    _label, unit = SIGNAL_LABELS.get(signal_name, (signal_name, ""))
    return unit


def get_signal_title(signal_name: str) -> str:
    return f"{get_signal_label(signal_name)} ({signal_name})"