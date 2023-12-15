import streamlit as st
import numpy as np
import pandas as pd
from io import BytesIO
from datetime import timedelta
from math import ceil
from datetime import datetime
from openpyxl.styles import Alignment

def distribute_to_trolleys(df):
    df['Необходимо листов'] = np.ceil(df['Количество изделий план'] / df['Количество на листе'])
    sorted_df = df.sort_values(by=['Тип теста', 'Температура Печи', 'Размер зуваляшки'], ascending=[True, True, False])
    
    trolley_info = {}
    trolley_counter = 1
    
    for _, row in sorted_df.iterrows():
        sheets_needed = row['Необходимо листов']
        
        while sheets_needed > 0:
            trolley_id = f'Вагонетка {trolley_counter}'
            if trolley_id not in trolley_info:
                trolley_info[trolley_id] = {
                    'Температура Печи': row['Температура Печи'],
                    'Время': row['Время'],
                    'Продукция': [],
                    'Листов в Вагонетке': 0
                }
            
            if (trolley_info[trolley_id]['Температура Печи'] != row['Температура Печи'] or
                trolley_info[trolley_id]['Листов в Вагонетке'] >= row['Количество листов в вагонетке']):
                trolley_counter += 1
                continue

            available_sheets = min(row['Количество листов в вагонетке'] - trolley_info[trolley_id]['Листов в Вагонетке'], sheets_needed)
            trolley_info[trolley_id]['Листов в Вагонетке'] += available_sheets

            trolley_info[trolley_id]['Продукция'].append({
                'Наименование товара': row['Наименование товара'],
                'Количество листов': available_sheets,
                'Количество на листе': row['Количество на листе']
            })

            sheets_needed -= available_sheets
    
    trolley_df_list = [dict(v, Вагонетка=k) for k, v in trolley_info.items()]
    return pd.DataFrame(trolley_df_list), trolley_info


def distribute_to_trolleys_sorted(df):
    # Конвертация 'кусок' в NaN или другое специфическое число, если необходимо
    df['Размер зуваляшки'] = pd.to_numeric(df['Размер зуваляшки'], errors='coerce').fillna(999)
    df['Тип теста'] = pd.Categorical(df['Тип теста'], categories=['сладкое', 'соленое'], ordered=True)
    df = df.sort_values(by=['Тип теста', 'Размер зуваляшки', 'Количество листов в вагонетке'], ascending=[True, False, False])
    df.reset_index(drop=True, inplace=True)
    return distribute_to_trolleys(df)



# Обновленная функция schedule_oven_operations с добавлением длительности и состава вагонетки
def schedule_oven_operations(start_shift, end_shift, num_ovens, change_trolley_time, change_temp_time, trolley_df, trolley_info):
    start_shift = datetime.strptime(start_shift, '%H:%M')
    end_shift = datetime.strptime(end_shift, '%H:%M')
    ovens_schedule = {f'Печь {i+1}': [] for i in range(num_ovens)}
    last_operation_time = {f'Печь {i+1}': start_shift for i in range(num_ovens)}
    current_temp = {f'Печь {i+1}': None for i in range(num_ovens)}
    
    trolley_composition = pd.DataFrame(columns=['Вагонетка', 'Состав'])
    
    for index, trolley in trolley_df.iterrows():
        next_oven = min(last_operation_time, key=last_operation_time.get)
        start_baking_time = last_operation_time[next_oven]
        
        if current_temp[next_oven] != trolley['Температура Печи']:
            start_baking_time += timedelta(minutes=change_temp_time)
            current_temp[next_oven] = trolley['Температура Печи']
        
        end_baking_time = start_baking_time + timedelta(minutes=trolley['Время'] + change_trolley_time)
        
        if end_baking_time <= end_shift:
            composition_list = [
                f"{prod_info['Наименование товара']}: {prod_info['Количество листов']} листов "
                f"({int(prod_info['Количество листов'] * prod_info['Количество на листе'])} штук)"
                for prod_info in trolley_info[trolley['Вагонетка']]['Продукция']
            ]
            composition = "\n".join(composition_list)
            total_sheets = trolley_info[trolley['Вагонетка']]['Листов в Вагонетке']  # Общее количество листов
            
            new_row = pd.DataFrame({
                'Вагонетка': [trolley['Вагонетка']],
                'Состав': [composition],
                'Листов': [total_sheets]  # Добавляем информацию о листах
            })
            
            trolley_composition = pd.concat([trolley_composition, new_row], ignore_index=True)

            ovens_schedule[next_oven].append({
                'Начало': start_baking_time.time().strftime('%H:%M'),
                'Конец': end_baking_time.time().strftime('%H:%M'),
                'Длительность': trolley['Время'],
                'Вагонетка': trolley['Вагонетка'],
                'Температура Печи': trolley['Температура Печи'],
                'Состав': composition
            })
            
            last_operation_time[next_oven] = end_baking_time
    
    return ovens_schedule, trolley_composition




# Функция для преобразования графика печей в DataFrame
def to_df_from_schedule(ovens_schedule):
    # Преобразование данных расписания в DataFrame
    oven_dfs = []
    for oven, schedule in ovens_schedule.items():
        oven_df = pd.DataFrame(schedule)
        oven_df.insert(0, 'Печь', oven)  # Добавление столбца с названием печи
        oven_dfs.append(oven_df)
    full_schedule_df = pd.concat(oven_dfs, ignore_index=True)
    return full_schedule_df

# Функция для сохранения DataFrame в Excel
def to_excel(oven_schedule_df, trolley_composition_df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        oven_schedule_df.to_excel(writer, sheet_name='Oven Schedule', index=False)
        trolley_composition_df.to_excel(writer, sheet_name='Trolley Composition', index=False)
        
        # Получаем активный объект workbook и sheet
        workbook  = writer.book
        worksheet = writer.sheets['Trolley Composition']
        
        # Применяем перенос текста ко всем ячейкам
        for row in worksheet.iter_rows():
            for cell in row:
                cell.alignment = Alignment(wrapText=True)

    return output.getvalue()


st.markdown('''<h3>Файл с данными</h3>''', unsafe_allow_html=True)
uploaded_file = st.file_uploader("Выберите XLSX файл с данными", accept_multiple_files=False)

if uploaded_file:
    df = pd.read_excel(uploaded_file)
    sorted_trolleys_df, trolley_info = distribute_to_trolleys_sorted(df)
    ovens_schedule, trolley_composition = schedule_oven_operations('13:00', '21:00', 3, 2, 5, sorted_trolleys_df, trolley_info)

    # Преобразование ovens_schedule в DataFrame
    oven_schedule_list = []
    for oven, schedule_list in ovens_schedule.items():
        for schedule in schedule_list:
            schedule['Печь'] = oven
            oven_schedule_list.append(schedule)
    oven_schedule_df = pd.DataFrame(oven_schedule_list)

    # Теперь вызываем функцию to_excel с необходимыми аргументами
    df_xlsx = to_excel(oven_schedule_df, trolley_composition)
    st.download_button(label='📥 Скачать план в Excel', data=df_xlsx, file_name='Backing_Plan.xlsx')

    
