import pandas as pd

df = pd.read_csv("./nist_lines.csv")
df['intens_numeric'] = pd.to_numeric(df['intens'].str.replace(r'[^0-9.]', '', regex=True), errors='coerce').fillna(0)
df['ritz_wl_numeric'] = pd.to_numeric(df['ritz_wl_vac(nm)'].str.replace(r'[^0-9.]', '', regex=True),
                                      errors='coerce')
df['obs_wl_numeric'] = pd.to_numeric(df['obs_wl_vac(nm)'].str.replace(r'[^0-9.]', '', regex=True),
                                     errors='coerce')
df['wavelength'] = df['obs_wl_numeric'].fillna(df['ritz_wl_numeric'])

new_df = df[['element', 'intens_numeric', 'wavelength']]
new_df.to_pickle('nist_lines.pkl')  # Save the DataFrame as pickle
