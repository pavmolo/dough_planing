import streamlit as st
import numpy as np
import pandas as pd
from io import BytesIO
from datetime import timedelta


# Теперь переопределим функцию create_full_baking_schedule с учетом наличия df_products_sorted
def create_full_baking_schedule(df, temp_for_oven1, start_time, reset_time=10, basket_interval=3):
    # Инициализация начального времени для каждой печи
    oven1_time = pd.to_datetime(start_time)
    oven2_time = pd.to_datetime(start_time)
    # Последняя температура для определения необходимости перенастройки
    last_temp_oven1 = temp_for_oven1
    last_temp_oven2 = None

    # Инициализация расписания выпекания
    baking_schedule = []

    # Перебор SKU для планирования по печам
    for index, row in df.iterrows():
        oven_time = oven1_time if row['Температура Печи'] == temp_for_oven1 else oven2_time
        oven_name = "Печь 1" if row['Температура Печи'] == temp_for_oven1 else "Печь 2"
        last_temp = last_temp_oven1 if oven_name == "Печь 1" else last_temp_oven2

        # Если температура изменилась, добавляем время на перенастройку
        if last_temp != row['Температура Печи']:
            baking_schedule.append([oven_name, "Перенастройка", "", last_temp, oven_time, "", "", reset_time])
            oven_time += timedelta(minutes=reset_time)

        # Планирование выпекания для каждой вагонетки
        for basket in range(1, row['Кол-во вагонеток'] + 1):
            baking_schedule.append([oven_name, row['Наименование товара'], basket, row['Температура Печи'], oven_time, oven_time - timedelta(hours=1.4), oven_time - timedelta(hours=3.3), row['Время']])
            oven_time += timedelta(minutes=row['Время'] + basket_interval)

        # Обновляем время последней выпекаемой вагонетки и температуру для печи
        if oven_name == "Печь 1":
            oven1_time = oven_time
            last_temp_oven1 = row['Температура Печи']
        else:
            oven2_time = oven_time
            last_temp_oven2 = row['Температура Печи']
        df = pd.DataFrame(baking_schedule, columns=["Печь", "Наименование товара", "Вагонетка", "Температура Печи", "Время начала выпекания", "Время формовки", "Время замеса", "Длительность"])
        # Преобразование строк в datetime объекты, а затем форматирование их как 'HH:MM'
        df['Время начала выпекания'] = pd.to_datetime(df['Время начала выпекания']).dt.strftime('%H:%M')
        df['Время формовки'] = pd.to_datetime(df['Время формовки']).dt.strftime('%H:%M')
        df['Время замеса'] = pd.to_datetime(df['Время замеса']).dt.strftime('%H:%M')

    return df

def to_excel():
    output = BytesIO()
    writer = pd.ExcelWriter(output, engine='xlsxwriter')
    with writer as w:
        for i in final_res:
            i.to_excel(writer, sheet_name=i["Печь"].unique()[0], index=False)
    writer._save()
    return output.getvalue()


st.markdown('''<h3>Файл с данными</h3>''', unsafe_allow_html=True)
df = st.file_uploader("Выберите XLSX файл с данными", accept_multiple_files=False)
if df: 
  df = pd.read_excel(df)
  st.dataframe(df)
  df_products = df
  df_products_sorted = df_products.sort_values(by=['Температура Печи'], ascending=[False])
  final_res = []
  shift_start = '13:00'
  for i in df_products_sorted["Температура Печи"].unique():
      full_baking_schedule = create_full_baking_schedule(df_products_sorted, i, shift_start)
      full_baking_schedule = full_baking_schedule[full_baking_schedule['Печь'] == "Печь 1"]
      full_baking_schedule["Печь"] = f'Печ режим {i}'
      final_res.append(full_baking_schedule)
  
df_xlsx = to_excel()
st.download_button(label='📥 Скачать план в Excel', data=df_xlsx, file_name='Backing_Plan.xlsx')
    
