import streamlit as st
import numpy as np
import pandas as pd
from io import BytesIO

st.markdown('''<h3>Файл с данными</h3>''', unsafe_allow_html=True)
master_data_file = st.file_uploader("Выберите XLSX файл с мастер данными", accept_multiple_files=False)
