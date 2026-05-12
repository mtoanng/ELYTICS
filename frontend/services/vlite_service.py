
import os
import pandas as pd
import numpy as np
from scipy.optimize import fmin

# --- Physical Constants and Parameter Classes ---

class Phys:
    def __init__(self):
        self.Rgas = 8.3145      # [J/(mol K)], universal gas constant
        self.Fara = 96485       # [sA/mol], Faraday's constant
        self.rhoW = 988         # [kg/m^3], density water @ 80 deg. C
        self.cW = 4184          # [J(kg K)], specific heat water
        self.Vth = 1.48         # [V], thermo-neutral voltage

class ParamDefault:
    def __init__(self):
        self.OCVE00 = 1.229      # [V]
        self.OCVee = 8.50e-4     # [V/K]
        self.OCVTref = 298       # [K]
        self.OCVpref = 1         # [bar]
        self.memT0 = 1268        # [K]
        self.memSigLa = 33.754   # [1/(Ohm m)]
        self.memSig0 = 21.412    # [1/(Ohm m)]
        self.CCMG = 52649        # [J/mol], Gibbs exchange current density temperature pardefault
        self.CCMj00 = 6.0e7      # [A/m^2], reference exchange current density
        self.CCMnval = 1.6       # [-], valency for total redox reaction
        self.lambda_val = 25     # [-], water content in membrane (0<lambda<30)
        self.ICRress = 50e-7     # [Ohm m^2], cell 'ICR' specific resistivity

class FitFix:
    def __init__(self):
        self.OCVE00 = 0
        self.OCVee = 0
        self.OCVTref = 0
        self.OCVpref = 0
        self.memT0 = 0
        self.memSigLa = 0
        self.memSig0 = 0
        self.CCMG = 0
        self.CCMj00 = 1
        self.CCMnval = 1
        self.lambda_val = 0
        self.ICRress = 1

# --- Data Handling ---

class PolcurveData:
    def __init__(self, df, df_meta=None):

        # Defaults
        self.nrcells = 6
        self.aact = 0.135
        self.memH = 80

        # Override with meta if available
        if df_meta is not None:
            try:
                self.nrcells = int(df_meta['number_of_cells'].iloc[0])
            except Exception:
                pass
            try:
                self.aact = float(df_meta['active_area_per_cell'].iloc[0])
            except Exception:
                pass
            try:
                self.memH = float(df_meta['ccm_thickness'].iloc[0])
            except Exception:
                pass

        # Map DataFrame columns to expected variable names
        # Ensure event_short_id column exists
        if 'event_short_id' not in df.columns and 'event_id' in df.columns and 'order_id' in df.columns:
            df = df.copy()
            df['event_short_id'] = df.apply(lambda row: f"{row['order_id']}_{str(row['event_id']).split('_')[-1]}", axis=1)
        self.data = {
            'jStck': df['jStck'].to_numpy(),        # [A/cm^2]
            'uCell': df['uCell'].to_numpy(),        # [V]
            'tAndeIn': df['tAndeIn'].to_numpy(),    # [oC]
            'tAndeOut': df['tAndeOut'].to_numpy(),  # [oC]
            'pAndeIn': df['pAndeIn'].to_numpy(),    # [barg]
            'pAndeOut': df['pAndeOut'].to_numpy(),  # [barg]
            'pCtdeIn': df['pCtdeIn'].to_numpy(),    # [barg]
            'pCtdeOut': df['pCtdeOut'].to_numpy(),  # [barg]
            'vfAndeIn': df['vfAndeIn'].to_numpy(),  # [l/min]
            'event_short_id': df['event_short_id'].iloc[0] if 'event_short_id' in df.columns and len(df) > 0 else 'event_1'
        }

# --- Shared Input Construction ---
def polcurve_input_from_data(df, df_meta=None):
    """
    Build the input dictionary for stackup/model calculation from polcurve data and meta.
    Handles nrcells, aact, memH, and all required columns.
    """
    polcurve = PolcurveData(df, df_meta)
    testdata = polcurve.data
    nrcells = polcurve.nrcells
    aact = polcurve.aact
    memH = polcurve.memH

    testj = testdata['jStck']            # [A/cm^2]
    testV = testdata['uCell']            # [V]
    testTWin = testdata['tAndeIn']       # [oC]
    testTWout = testdata['tAndeOut']     # [oC]
    testpWanin = testdata['pAndeIn']     # [barg]
    testpWanout = testdata['pAndeOut']   # [barg]
    testpWcain = testdata['pCtdeIn']     # [barg]
    testpWcaout = testdata['pCtdeOut']   # [barg]
    testQW = testdata['vfAndeIn']        # [l/min]
    event = testdata['event_short_id']

    inp = {}
    arraysz = testj.shape[0]
    inp['memH'] = memH * 1e-6              # [m], membrane thickness
    inp['modelj'] = 1e4 * testj            # [A/m^2], current density (converted from A/cm^2)
    inp['modelQW'] = testQW / 60000 / nrcells if nrcells else testQW / 60000 # [m^3/s], water flow rate, per cell
    inp['modelTW'] = testTWin + 273        # [K], water/cell temperature (converted from oC)

    # Pressure handling - NaN check still applies
    if np.sum(np.isnan(testpWanin)) == 0 and np.sum(np.isnan(testpWanout)) == 0:
        inp['modelpan'] = 1 + (testpWanin + testpWanout) / 2 # [bar], average of in and out data, translated to absolute pressure
    else:
        inp['modelpan'] = np.ones(arraysz) # [bar], switch to default value

    if np.sum(np.isnan(testpWcain)) == 0 and np.sum(np.isnan(testpWcaout)) == 0:
        inp['modelpca'] = 1 + (testpWcain + testpWcaout) / 2 # [bar], average of in and out data, translated to absolute pressure
    else:
        inp['modelpca'] = np.ones(arraysz) # [bar], switch to default value

    inp['modelAact'] = aact * 1e-4   # [m^2], active area (converted from cm^2)
    inp['event'] = event             # For plot title
    inp['testV'] = testV             # Tested voltage
    inp['testDTW'] = testTWout - testTWin # Tested temperature rise
    return inp

# --- Parameter Array Utilities ---

def struct2pararray2(parstruct):
    """Convert parameter structure to array."""
    pararray = np.zeros(12)
    pararray[0] = parstruct.OCVE00
    pararray[1] = parstruct.OCVee
    pararray[2] = parstruct.OCVTref
    pararray[3] = parstruct.OCVpref
    pararray[4] = parstruct.memT0
    pararray[5] = parstruct.memSigLa
    pararray[6] = parstruct.memSig0
    pararray[7] = parstruct.CCMG
    pararray[8] = parstruct.CCMj00
    pararray[9] = parstruct.CCMnval
    pararray[10] = parstruct.lambda_val
    pararray[11] = parstruct.ICRress
    return pararray

def pararray2struct2(pararray):
    """Convert parameter array to structure."""
    parstruct = ParamDefault()
    parstruct.OCVE00 = pararray[0]
    parstruct.OCVee = pararray[1]
    parstruct.OCVTref = pararray[2]
    parstruct.OCVpref = pararray[3]
    parstruct.memT0 = pararray[4]
    parstruct.memSigLa = pararray[5]
    parstruct.memSig0 = pararray[6]
    parstruct.CCMG = pararray[7]
    parstruct.CCMj00 = pararray[8]
    parstruct.CCMnval = pararray[9]
    parstruct.lambda_val = pararray[10]
    parstruct.ICRress = pararray[11]
    return parstruct

# --- Model Calculation Functions ---

def func_vlite13(inp, par, phys, NT):
    """
    Compute cell potential and temperature for V-lite model.
    """
    out = {}
    out['modelTcell'] = inp['modelTW']

    for i in range(NT):
        # Ensure all array-like inputs are numpy arrays for element-wise operations
        modelTcell_arr = np.array(out['modelTcell']) if isinstance(out['modelTcell'], (float, int)) else out['modelTcell']
        modelpan_arr = np.array(inp['modelpan']) if isinstance(inp['modelpan'], (float, int)) else inp['modelpan']
        modelpca_arr = np.array(inp['modelpca']) if isinstance(inp['modelpca'], (float, int)) else inp['modelpca']
        modelj_arr = np.array(inp['modelj']) if isinstance(inp['modelj'], (float, int)) else inp['modelj']
        modelAact_arr = np.array(inp['modelAact']) if isinstance(inp['modelAact'], (float, int)) else inp['modelAact']
        modelQW_arr = np.array(inp['modelQW']) if isinstance(inp['modelQW'], (float, int)) else inp['modelQW']

        out['Erev'] = par.OCVE00 - par.OCVee * (modelTcell_arr - par.OCVTref) + \
                      (phys.Rgas * modelTcell_arr / (4 * phys.Fara)) * \
                      np.log(modelpan_arr * modelpca_arr**2 / par.OCVpref**3)
        out['etaICR'] = modelj_arr * par.ICRress
        out['etamem'] = (modelj_arr * inp['memH'] / (par.memSigLa * par.lambda_val - par.memSig0)) * \
                        np.exp(par.memT0 / modelTcell_arr)
        out['j0'] = par.CCMj00 * np.exp(-par.CCMG / (phys.Rgas * modelTcell_arr))
        out['etaact'] = (2 * phys.Rgas * modelTcell_arr / (par.CCMnval * phys.Fara)) * \
                        np.arcsinh(modelj_arr / (2 * out['j0']))
        out['V'] = out['Erev'] + out['etaICR'] + out['etamem'] + out['etaact']

        # Water temperature increase
        out['DTW'] = (out['V'] - phys.Vth) * modelAact_arr * modelj_arr / \
                     (phys.rhoW * phys.cW * modelQW_arr)

        # Update T
        out['modelTcell'] = inp['modelTW'] + out['DTW'] / 2

    return out

def func_fit2(pararray_fit, fitfix, pararraydefault, testV, inp, phys, NT):
    """
    Optimization function for fitting required parameters.
    """
    p_full = pararraydefault.copy()
    fit_indices = np.where(fitfix == 1)[0]
    if len(pararray_fit) != len(fit_indices):
        raise ValueError("Length of pararray_fit does not match number of fitted parameters.")
    p_full[fit_indices] = pararray_fit

    par = pararray2struct2(p_full)
    modelout = func_vlite13(inp, par, phys, NT)
    res = np.sqrt(np.sum((testV - modelout['V'])**2))

    # Regularization for lambda_val
    if fitfix[10] == 1:
        lambda_idx_in_fit = np.where(fit_indices == 10)[0][0]
        lambda_val_current = pararray_fit[lambda_idx_in_fit]
    else:
        lambda_val_current = pararraydefault[10]

    res = res + 1e-5 * (lambda_val_current - pararraydefault[10])**2
    return res

# --- Main Model Runner ---

def run_model(df, df_meta=None):
    """
    Run the V-lite model fit on the given DataFrame.
    If df_meta is provided, extract nrcells, aact, and memH from its first row.
    Returns inp, out for plotting (modelj, V).
    """

    # Physical Constants and Parameters
    phys = Phys()
    pardefault_obj = ParamDefault()
    pardefault_array = struct2pararray2(pardefault_obj)
    fitfix_obj = FitFix()
    fitfix_array = struct2pararray2(fitfix_obj)

    # V-lite parameters
    NT = 3
    pWandefault = 1 # [bar]
    pWcadefault = 1 # [bar]

    inp = polcurve_input_from_data(df, df_meta)
    testV = inp['testV']
    pd_array = struct2pararray2(pardefault_obj)
    initial_guess_for_fit = pd_array[fitfix_array == 1]
    fitted_indices = np.where(fitfix_array == 1)[0]

    try:
        # Capture the minimized residual value
        def fit_func_and_res(p_fit):
            res = func_fit2(p_fit, fitfix_array, pd_array, testV, inp, phys, NT)
            return res

        p_fit_optimized = fmin(
            fit_func_and_res,
            initial_guess_for_fit,
            disp=False,
            xtol=1e-6
        )
        # Calculate minimized residual
        minimized_res = fit_func_and_res(p_fit_optimized)
        psol_array = pd_array.copy()
        psol_array[fitted_indices] = p_fit_optimized
        parsol = pararray2struct2(psol_array)
        outsol = func_vlite13(inp, parsol, phys, NT)

        # Get errors 
        LSQerravg = 1000*np.sqrt(np.sum((outsol['V'] - inp['testV'])**2))/len(inp['testV'])  # [mV]
        # LSQerrmax       = 1000*max(abs(outsol.V - inp.testV));

        # Convert numpy arrays to lists for Dash serialization
        inp_serial = {k: (v.tolist() if isinstance(v, np.ndarray) else v) for k, v in inp.items()}
        out_serial = {k: (v.tolist() if isinstance(v, np.ndarray) else v) for k, v in outsol.items()}

        # Include parsol items in out_serial
        for k, v in vars(parsol).items():
            out_serial[k] = v
        # Add minimized residual to output
        out_serial['res'] = minimized_res
        out_serial['LSQerravg'] = LSQerravg

        return inp_serial, out_serial
    except Exception as e:
        raise RuntimeError(f"Model fit failed: {e}")
