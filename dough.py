import streamlit as st
import numpy as np
import pandas as pd
from io import BytesIO

st.markdown('''<h3>Файл с данными</h3>''', unsafe_allow_html=True)
df = st.file_uploader("Выберите XLSX файл с данными", accept_multiple_files=False)
if df: 
  df = pd.read_excel(df)
  st.dataframe(df)
