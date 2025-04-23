import pandas as pd
import numpy as np
from faker import Faker
from datetime import datetime, timedelta
import random
from tqdm import tqdm

def expand_dataset(input_file, output_file, target_rows=5_000_000, chunk_size=100000):
    # Загрузка исходных данных с указанием типов
    dtype_spec = {
        'mileage': 'Int64',
        'manufacture_year': 'Int64',
        'engine_displacement': 'Int64',
        'engine_power': 'Int64',
        'stk_year': 'Int64',
        'door_count': 'Int64',
        'seat_count': 'Int64'
    }
    
    df = pd.read_csv(input_file, dtype=dtype_spec)
    original_rows = len(df)
    print(f"Original dataset size: {original_rows} rows")
    
    if original_rows >= target_rows:
        print("Dataset already meets target size")
        return
    
    # Инициализация Faker
    fake = Faker()
    
    # Функция для модификации строки с учётом типов данных
    def modify_row(base_row):
        new_row = base_row.copy()
        
        # Целочисленные поля с обработкой NaN
        int_fields = {
            'mileage': (0.1, 0, None),        # (std_factor, min_value, max_value)
            'manufacture_year': (1, 1980, 2023),
            'engine_displacement': (0.05, 0, None),
            'engine_power': (0.1, 0, None),
            'door_count': (0, 2, 7),         # Нулевое отклонение, только допустимые значения
            'seat_count': (0, 2, 9),
            'stk_year': (0, None, None)       # Без изменений (как в примере)
        }
        
        for field, (std_factor, min_val, max_val) in int_fields.items():
            if field in new_row and pd.notna(base_row[field]):
                original_value = base_row[field]
                if std_factor > 0:
                    new_value = original_value * (1 + random.gauss(0, std_factor))
                    new_value = int(round(new_value))
                else:
                    new_value = original_value
                
                if min_val is not None:
                    new_value = max(min_val, new_value)
                if max_val is not None:
                    new_value = min(max_val, new_value)
                
                new_row[field] = new_value
        
        # Дробные числа
        if 'price_eur' in new_row and pd.notna(base_row['price_eur']):
            new_row['price_eur'] = max(100, base_row['price_eur'] * (1 + random.gauss(0, 0.15)))
        
        # Модификация дат
        date_change = random.randint(-180, 180)
        date_fields = ['date_created', 'date_last_seen']
        
        for field in date_fields:
            if field in new_row and pd.notna(base_row[field]):
                try:
                    dt_str = str(base_row[field]).split('+')[0].strip()
                    dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S.%f")
                    new_dt = dt + timedelta(days=date_change)
                    if field == 'date_last_seen':
                        new_dt += timedelta(days=random.randint(1, 30))
                    new_row[field] = new_dt.strftime("%Y-%m-%d %H:%M:%S.%f") + "+00"
                except:
                    pass
        
        # Категориальные поля
        categorical_fields = {
            'transmission': (0.1, ['man', 'auto', None]),
            'fuel_type': (0.05, ['diesel', 'gasoline', 'hybrid', 'electric', None]),
            'color_slug': (0.05, ['black', 'white', 'silver', 'gray', 'blue', 'red', None]),
            'body_type': (0.05, ['sedan', 'hatchback', 'suv', 'coupe', 'convertible', None])
        }
        
        for field, (change_prob, options) in categorical_fields.items():
            if field in new_row and random.random() < change_prob:
                new_row[field] = random.choice(options)
        
        return new_row
    
    # Генерация новых данных по чанкам
    rows_to_generate = target_rows - original_rows
    chunks = []
    chunk_count = (rows_to_generate // chunk_size) + 1
    
    print(f"Generating {rows_to_generate:,} new rows in {chunk_count} chunks...")
    
    for _ in tqdm(range(chunk_count), desc="Processing chunks"):
        chunk_rows = min(chunk_size, rows_to_generate - len(chunks) * chunk_size)
        if chunk_rows <= 0:
            break
        
        base_indices = np.random.randint(0, original_rows, size=chunk_rows)
        new_chunk = df.iloc[base_indices].copy()
        new_chunk = new_chunk.apply(modify_row, axis=1)
        chunks.append(new_chunk)
    
    # Объединяем и сохраняем
    new_df = pd.concat(chunks, ignore_index=True)
    expanded_df = pd.concat([df, new_df], ignore_index=True)
    expanded_df = expanded_df.sample(frac=1, random_state=42).reset_index(drop=True)
    
    # Приводим типы перед сохранением
    for field in dtype_spec:
        if field in expanded_df:
            expanded_df[field] = pd.to_numeric(expanded_df[field], errors='coerce').astype('Int64')
    
    expanded_df.to_csv(output_file, index=False)
    print(f"\nDataset expanded to {len(expanded_df):,} rows")
    print(f"Saved to {output_file}")


# Пример использования
if __name__ == "__main__":
    input_file = "dataset_small.csv"  # Укажите ваш исходный файл
    output_file = "dataset_extended.csv"
    
    expand_dataset(input_file, output_file)
    