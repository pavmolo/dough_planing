import streamlit as st
import numpy as np
import pandas as pd
from io import BytesIO
from datetime import timedelta
from math import ceil
from datetime import datetime

def distribute_to_trolleys(df):
    df['Необходимо листов'] = np.ceil(df['Количество изделий план'] / df['Количество на листе'])
    sorted_df = df.sort_values(by=['Тип теста', 'Температура Печи'])
    
    # Словарь для хранения информации о вагонетках
    trolley_info = {}
    
    trolley_counter = 1
    for (test_type, temp), group in sorted_df.groupby(['Тип теста', 'Температура Печи'], observed=True):
        current_trolley_sheets = 0
        group = group.reset_index(drop=True)

        for idx, row in group.iterrows():
            sheets_needed = row['Необходимо листов']
            while sheets_needed > 0:
                trolley_id = f'Вагонетка {trolley_counter}'
                if trolley_id not in trolley_info:
                    # Для каждой новой вагонетки сохраняем температуру печи и время выпекания
                    trolley_info[trolley_id] = {
                        'Температура Печи': temp,
                        'Время': row['Время'],
                        'Продукция': []
                    }

                available_sheets = min(row['Количество листов в вагонетке'] - current_trolley_sheets, sheets_needed)
                if available_sheets <= 0:
                    trolley_counter += 1
                    current_trolley_sheets = 0
                    continue
                
                # Добавляем информацию о продукте в список продукции текущей вагонетки
                trolley_info[trolley_id]['Продукция'].append((row['Наименование товара'], available_sheets, int(sheets_needed * row['Количество на листе'])))

                sheets_needed -= available_sheets
                current_trolley_sheets += available_sheets
                if current_trolley_sheets >= row['Количество листов в вагонетке']:
                    trolley_counter += 1
                    current_trolley_sheets = 0

    # Преобразование словаря trolley_info в DataFrame
    trolley_df_list = []
    for trolley_id, info in trolley_info.items():
        # Создание словаря для каждой вагонетки
        trolley_dict = {
            'Вагонетка': trolley_id,
            'Температура Печи': info['Температура Печи'],
            'Время': info['Время']
        }
        # Собираем состав продукции в вагонетке
        for product_info in info['Продукция']:
            product_name, sheets, quantity = product_info
            trolley_dict[product_name] = f"{sheets} листов ({quantity} штук)"
        trolley_df_list.append(trolley_dict)

    trolley_df = pd.DataFrame(trolley_df_list)
    return trolley_df



def distribute_to_trolleys_sorted(df):
    # Конвертация 'кусок' в NaN или другое специфическое число, если необходимо
    df['Размер зуваляшки'] = pd.to_numeric(df['Размер зуваляшки'], errors='coerce').fillna(999)
    df['Тип теста'] = pd.Categorical(df['Тип теста'], categories=['сладкое', 'соленое'], ordered=True)
    df = df.sort_values(by=['Тип теста', 'Размер зуваляшки', 'Количество листов в вагонетке'], ascending=[True, False, False])
    df.reset_index(drop=True, inplace=True)
    return distribute_to_trolleys(df)



# Обновленная функция schedule_oven_operations с добавлением длительности и состава вагонетки
def schedule_oven_operations(start_shift, end_shift, num_ovens, change_trolley_time, change_temp_time, df):
    start_shift = datetime.strptime(start_shift, '%H:%M')
    end_shift = datetime.strptime(end_shift, '%H:%M')
    ovens_schedule = {f'Печь {i+1}': [] for i in range(num_ovens)}
    last_operation_time = {f'Печь {i+1}': start_shift for i in range(num_ovens)}
    current_temp = {f'Печь {i+1}': None for i in range(num_ovens)}
    
    # Создание DataFrame для состава вагонетки
    trolley_composition = pd.DataFrame(columns=['Вагонетка', 'Состав'])

    for _, trolley in df.iterrows():
        next_oven = min(last_operation_time, key=last_operation_time.get)
        start_baking_time = last_operation_time[next_oven]
        if current_temp[next_oven] != trolley['Температура Печи']:
            start_baking_time += timedelta(minutes=change_temp_time)
            current_temp[next_oven] = trolley['Температура Печи']

        end_baking_time = start_baking_time + timedelta(minutes=trolley['Время'] + change_trolley_time)

        if end_baking_time <= end_shift:
            # Формирование состава вагонетки
            composition = ", ".join([f"{name}: {sheets} листов ({int(sheets * row['Количество на листе'])} штук)"
                                     for name, sheets in trolley.items() if name != 'Необходимо листов'])
            
            # Добавление записи о составе вагонетки
            trolley_composition = trolley_composition.append({
                'Вагонетка': trolley.name,
                'Состав': composition
            }, ignore_index=True)

            ovens_schedule[next_oven].append({
                'Начало': start_baking_time.time(),
                'Конец': end_baking_time.time(),
                'Длительность': trolley['Время'],
                'Вагонетка': trolley.name,
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
    with pd.ExcelWriter(output) as writer:
        oven_schedule_df.to_excel(writer, sheet_name='Oven Schedule', index=False)
        trolley_composition_df.to_excel(writer, sheet_name='Trolley Composition', index=False)
    return output.getvalue()


st.markdown('''<h3>Файл с данными</h3>''', unsafe_allow_html=True)
uploaded_file = st.file_uploader("Выберите XLSX файл с данными", accept_multiple_files=False)

if uploaded_file:
    # Считывание данных из файла в DataFrame
    df = pd.read_excel(uploaded_file)
    st.dataframe(df)
    
    # Передача DataFrame в функции
    sorted_trolleys_df = distribute_to_trolleys_sorted(df)
    ovens_schedule, trolley_composition = schedule_oven_operations('13:00', '21:00', 3, 2, 5, sorted_trolleys_df)
    oven_schedule_df = to_df_from_schedule(ovens_schedule)
    trolley_composition_df = to_df_from_list(trolley_composition)
    
    # Вызов функции to_excel для создания файла Excel из DataFrame
    df_xlsx = to_excel(oven_schedule_df, trolley_composition_df)
    st.download_button(label='📥 Скачать план в Excel', data=df_xlsx, file_name='Backing_Plan.xlsx')
    
