#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Объединенный сервер FastAPI с подключением к удаленной БД и всеми функциями
"""

from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict
from typing import List, Optional
from contextlib import asynccontextmanager
import json
import os
import csv
import uuid
from datetime import datetime
import shutil
from sqlalchemy.orm import Session

# Импортируем настройки удаленной базы данных
from .database_remote import get_db, DatabaseManager, create_tables, test_connection

# Импортируем функции из button_for_front.py
from .button_for_front import (
    upload_client_file, 
    convert_to_json, 
    process_json_to_locations,
    process_client_file_complete,
    register_user,
    find_user_by_phone,
    get_user_available_locations,
    mark_location_visited,
    set_stay_period,
    check_stay_period
)

# Функция для управления жизненным циклом приложения
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("[INFO] Проверка подключения к базе данных...")
    if test_connection():
        print("[INFO] Создание/проверка таблиц...")
        create_tables()
        print("[OK] База данных готова к работе")
    else:
        print("[WARNING] Не удалось подключиться к базе данных. API будет работать в ограниченном режиме.")
    yield
    # Shutdown (если нужно что-то закрыть)

# Создаем экземпляр FastAPI
app = FastAPI(
    title="GeoData API - Unified",
    description="Объединенный REST API для работы с геоданными адресов с поддержкой удаленной PostgreSQL",
    version="3.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# Настройка CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # В продакшене укажите конкретные домены
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Монтирование статических файлов
app.mount("/static", StaticFiles(directory="frontend"), name="static")

# Модели данных (Pydantic)
class AddressBase(BaseModel):
    address: str
    address1: str
    lat: float
    lon: float
    client_level: str = "Standart"

class AddressCreate(AddressBase):
    pass

class AddressUpdate(BaseModel):
    address: Optional[str] = None
    address1: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    client_level: Optional[str] = None

class Address(AddressBase):
    id: int
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

# Новые модели для дополнительных эндпоинтов
class RouteRequest(BaseModel):
    client_ids: List[int]
    start_lat: float
    start_lon: float
    end_lat: Optional[float] = None
    end_lon: Optional[float] = None
    algorithm: str = "ai"  # "ai" или "base"

class RouteResponse(BaseModel):
    route_id: str
    total_distance: float
    total_time: float
    waypoints: List[dict]
    optimized: bool

class ClientStatusUpdate(BaseModel):
    client_id: int
    visited: bool
    visit_time: Optional[str] = None
    notes: Optional[str] = None

class ExportRequest(BaseModel):
    format: str = "json"  # "json", "csv", "excel"
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    client_levels: Optional[List[str]] = None

# Новые модели для работы с button_for_front.py
class UserRegistration(BaseModel):
    first_name: str
    last_name: str
    phone_number: str
    password: str

class UserLogin(BaseModel):
    phone_number: str
    password: str

class LocationVisit(BaseModel):
    user_id: int
    location_id: int

class StayPeriodRequest(BaseModel):
    user_id: int
    days: int


# Базовые эндпоинты
@app.get("/")
async def root():
    """Главная страница фронтенда index.html"""
    return FileResponse("frontend/index.html")

@app.get("/api")
async def api_root():
    """API корневой эндпоинт"""
    return {
        "message": "Добро пожаловать в GeoData API - Объединенная версия!",
        "version": "3.0.0",
        "docs": "/docs",
        "database": "Remote PostgreSQL",
        "features": [
            "CRUD операции с адресами",
            "Поиск ближайших адресов",
            "AI и базовые маршруты",
            "Загрузка файлов",
            "Статистика и отчеты",
            "Управление посещениями"
        ]
    }

@app.get("/health")
async def health_check(db: Session = Depends(get_db)):
    """Проверка состояния API и базы данных"""
    try:
        db_manager = DatabaseManager(db)
        addresses_count = db_manager.get_addresses_count()
        
        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "addresses_count": addresses_count,
            "database": "connected",
            "database_type": "PostgreSQL",
            "version": "3.0.0"
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "timestamp": datetime.now().isoformat(),
            "error": str(e),
            "database": "disconnected"
        }

# CRUD операции для адресов с PostgreSQL
@app.get("/addresses", response_model=List[Address])
async def get_addresses(
    skip: int = 0,
    limit: int = 100,
    client_level: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Получить список всех адресов с возможностью фильтрации"""
    db_manager = DatabaseManager(db)
    addresses = db_manager.get_addresses(skip=skip, limit=limit, client_level=client_level)
    return addresses

@app.get("/addresses/stats")
async def get_address_stats(db: Session = Depends(get_db)):
    """Получить статистику по адресам"""
    db_manager = DatabaseManager(db)
    stats = db_manager.get_addresses_stats()
    return stats

@app.get("/addresses/{address_id}", response_model=Address)
async def get_address(address_id: int, db: Session = Depends(get_db)):
    """Получить конкретный адрес по ID"""
    db_manager = DatabaseManager(db)
    address = db_manager.get_address_by_id(address_id)
    if not address:
        raise HTTPException(status_code=404, detail="Адрес не найден")
    return address

@app.post("/addresses", response_model=Address)
async def create_address(address: AddressCreate, db: Session = Depends(get_db)):
    """Создать новый адрес"""
    db_manager = DatabaseManager(db)
    address_data = address.model_dump()
    new_address = db_manager.create_address(address_data)
    return new_address

@app.put("/addresses/{address_id}", response_model=Address)
async def update_address(
    address_id: int, 
    address_update: AddressUpdate, 
    db: Session = Depends(get_db)
):
    """Обновить адрес"""
    db_manager = DatabaseManager(db)
    update_data = address_update.model_dump(exclude_unset=True)
    updated_address = db_manager.update_address(address_id, update_data)
    if not updated_address:
        raise HTTPException(status_code=404, detail="Адрес не найден")
    return updated_address

@app.delete("/addresses/{address_id}")
async def delete_address(address_id: int, db: Session = Depends(get_db)):
    """Удалить адрес"""
    db_manager = DatabaseManager(db)
    deleted_address = db_manager.delete_address(address_id)
    if not deleted_address:
        raise HTTPException(status_code=404, detail="Адрес не найден")
    return {"message": "Адрес удален", "deleted_address": deleted_address}

# Специальные эндпоинты для геоданных
@app.get("/addresses/nearby")
async def get_nearby_addresses(
    lat: float,
    lon: float,
    radius: float = 1.0,
    limit: int = 10,
    db: Session = Depends(get_db)
):
    """Получить адреса в радиусе от указанных координат"""
    import math
    
    def calculate_distance(lat1, lon1, lat2, lon2):
        """Вычисляет расстояние между двумя точками в километрах"""
        R = 6371  # Радиус Земли в км
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = (math.sin(dlat/2) * math.sin(dlat/2) + 
             math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * 
             math.sin(dlon/2) * math.sin(dlon/2))
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        return R * c
    
    db_manager = DatabaseManager(db)
    all_addresses = db_manager.get_addresses(limit=1000)  # Получаем больше адресов для поиска
    
    nearby_addresses = []
    for address in all_addresses:
        distance = calculate_distance(lat, lon, address.lat, address.lon)
        if distance <= radius:
            address_dict = {
                "id": address.id,
                "address": address.address,
                "address1": address.address1,
                "lat": address.lat,
                "lon": address.lon,
                "client_level": address.client_level,
                "distance_km": round(distance, 3)
            }
            nearby_addresses.append(address_dict)
    
    # Сортируем по расстоянию
    nearby_addresses.sort(key=lambda x: x["distance_km"])
    
    return nearby_addresses[:limit]

# Эндпоинт для массовой загрузки данных
@app.post("/addresses/bulk")
async def create_addresses_bulk(addresses: List[AddressCreate], db: Session = Depends(get_db)):
    """Создать несколько адресов одновременно"""
    db_manager = DatabaseManager(db)
    new_addresses = []
    
    for address in addresses:
        address_data = address.model_dump()
        new_address = db_manager.create_address(address_data)
        new_addresses.append(new_address)
    
    return {
        "message": f"Создано {len(new_addresses)} адресов",
        "created_addresses": new_addresses
    }

# ===== ЭНДПОИНТЫ ДЛЯ ЗАГРУЗКИ ФАЙЛОВ =====

@app.post("/api/upload")
async def upload_clients_file(
    file: UploadFile = File(...),
    address: Optional[str] = Form(None),
    period: Optional[str] = Form(None),
    lat: Optional[str] = Form(None),
    lon: Optional[str] = Form(None),
    user_id: Optional[int] = Form(None),
    db: Session = Depends(get_db)
):
    """Загрузка файла клиентов с дополнительными параметрами"""
    if not file.filename:
        raise HTTPException(status_code=400, detail="Файл не выбран")
    
    # Проверяем расширение файла (только CSV и Excel)
    allowed_extensions = ('.csv', '.xlsx', '.xls')
    if not file.filename.lower().endswith(allowed_extensions):
        raise HTTPException(
            status_code=400, 
            detail=f"Поддерживаются только файлы: CSV (.csv), Excel (.xlsx, .xls). Получен файл: {file.filename}"
        )
    
    # Создаем папку для загруженных файлов
    upload_dir = "uploads"
    os.makedirs(upload_dir, exist_ok=True)
    
    # Генерируем уникальное имя файла
    file_id = str(uuid.uuid4())
    file_extension = os.path.splitext(file.filename)[1].lower()
    file_path = os.path.join(upload_dir, f"{file_id}{file_extension}")
    
    try:
        # Сохраняем файл
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Обрабатываем файл в зависимости от типа
        processed_data = []
        print(f"Обработка файла: {file.filename} (расширение: {file_extension})")
        if file_extension == '.csv':
            processed_data = process_csv_file(file_path)
            print(f"Обработано CSV строк: {len(processed_data)}")
        elif file_extension in ('.xlsx', '.xls'):
            processed_data = process_excel_file(file_path)
            print(f"Обработано Excel строк: {len(processed_data)}")
        else:
            raise Exception(f"Неподдерживаемый формат файла: {file.filename}")
        
        if not processed_data:
            raise Exception("Файл не содержит данных для обработки")
        
        # Сохраняем адреса в базу данных
        db_manager = DatabaseManager(db)
        
        # Определяем user_id (если не указан, используем 1 как дефолтный)
        if user_id is None:
            user_id = 1
        else:
            try:
                user_id = int(user_id)
            except (ValueError, TypeError):
                user_id = 1
        
        # Проверяем, существует ли пользователь
        user = db_manager.get_user_by_id(user_id)
        if not user:
            # Создаем дефолтного пользователя, если его нет
            print(f"⚠️ Пользователь с ID {user_id} не найден, создаем дефолтного пользователя")
            try:
                from .database_remote import User
                # Проверяем, не существует ли уже пользователь с таким user_id
                existing_user = db.query(User).filter(User.user_id == user_id).first()
                if not existing_user:
                    default_user = User(
                        user_id=user_id,
                        first_name="Default",
                        last_name="User",
                        phone_number=f"+799999999{user_id:02d}",
                        password_hash="default"
                    )
                    db.add(default_user)
                    db.commit()
                    db.refresh(default_user)
                    print(f"✓ Создан дефолтный пользователь с ID {user_id}")
                else:
                    print(f"✓ Пользователь с ID {user_id} уже существует")
            except Exception as e:
                import traceback
                print(f"⚠️ Не удалось создать дефолтного пользователя: {e}")
                print(f"  Traceback: {traceback.format_exc()}")
                # Если не удалось создать пользователя, пробуем использовать существующего
                existing_users = db_manager.get_all_users()
                if existing_users:
                    user_id = existing_users[0].user_id
                    print(f"⚠️ Используем существующего пользователя с ID {user_id}")
                else:
                    raise Exception(f"Не удалось создать или найти пользователя. Ошибка: {e}")
        
        # Очищаем старые адреса этого пользователя перед загрузкой новых
        try:
            deleted_count = db_manager.delete_addresses_by_user(user_id)
            print(f"🗑️ Удалено старых адресов пользователя {user_id}: {deleted_count}")
        except Exception as e:
            print(f"⚠️ Ошибка при очистке старых адресов: {e}")
            # Продолжаем работу, даже если не удалось очистить
        
        created_addresses = []
        errors_count = 0
        for idx, address_data in enumerate(processed_data):
            try:
                # Проверяем обязательные поля
                if 'lat' not in address_data or 'lon' not in address_data:
                    print(f"Пропущена запись {idx}: отсутствуют координаты")
                    errors_count += 1
                    continue
                
                # Убеждаемся, что address1 заполнено (обязательное поле в БД)
                if 'address1' not in address_data or not address_data.get('address1'):
                    address_data['address1'] = address_data.get('address', '')
                
                # Убеждаемся, что address заполнено
                if 'address' not in address_data or not address_data.get('address'):
                    address_data['address'] = address_data.get('address1', '')
                
                # Убеждаемся, что client_level заполнен
                if 'client_level' not in address_data or not address_data.get('client_level'):
                    address_data['client_level'] = 'Standart'
                
                # Добавляем user_id к данным адреса
                address_data['user_id'] = user_id
                
                # Проверяем, что все обязательные поля присутствуют
                required_fields = ['address', 'address1', 'lat', 'lon', 'user_id']
                missing_fields = [f for f in required_fields if f not in address_data or address_data[f] is None]
                if missing_fields:
                    print(f"✗ Пропущена запись {idx}: отсутствуют обязательные поля: {missing_fields}")
                    errors_count += 1
                    continue
                
                print(f"Сохранение адреса {idx+1}/{len(processed_data)} для пользователя {user_id}: {address_data.get('address', 'N/A')}")
                print(f"  Данные: {address_data}")
                
                try:
                    new_address = db_manager.create_address(address_data)
                    created_addresses.append(new_address)
                    print(f"✓ Создан адрес ID={new_address.id} для пользователя {user_id}: {new_address.address}")
                except Exception as db_error:
                    import traceback
                    print(f"✗ Ошибка БД при создании адреса {idx}: {db_error}")
                    print(f"  Данные адреса: {address_data}")
                    print(f"  Traceback: {traceback.format_exc()}")
                    
                    # Проверяем, возможно проблема в структуре таблицы
                    if "user_id" in str(db_error) or "column" in str(db_error).lower() or "не существует" in str(db_error).lower():
                        print(f"⚠️ ВОЗМОЖНО, ТАБЛИЦА addresses НЕ ИМЕЕТ КОЛОНКИ user_id!")
                        print(f"⚠️ ВЫПОЛНИТЕ МИГРАЦИЮ: psql -U nikitaurovsky -d hack_chapmani -f back/migrate_add_user_id.sql")
                    errors_count += 1
                    continue
            except Exception as e:
                import traceback
                print(f"✗ Общая ошибка создания адреса {idx}: {e}")
                print(f"  Traceback: {traceback.format_exc()}")
                errors_count += 1
                continue
        
        print(f"Успешно создано адресов: {len(created_addresses)}, ошибок: {errors_count}")
        
        if not created_addresses:
            error_msg = "Не удалось сохранить ни одной записи в базу данных. Проверьте формат данных и логи ошибок."
            if errors_count > 0:
                error_msg += " Возможно, таблица addresses не имеет колонки user_id. Выполните миграцию: psql -U nikitaurovsky -d hack_chapmani -f back/migrate_add_user_id.sql"
            raise Exception(error_msg)
        
        # Сохраняем информацию о файле в базу данных
        file_info = {
            "file_id": file_id,
            "original_name": file.filename,
            "file_path": file_path,
            "upload_time": datetime.now(),
            "records_count": len(created_addresses),
            "status": "processed"
        }
        try:
            db_manager.create_uploaded_file(file_info)
            print(f"Информация о файле сохранена: {file_id}")
        except Exception as e:
            print(f"Ошибка сохранения информации о файле: {e}")
            # Не прерываем выполнение, если не удалось сохранить метаданные
        
        # Форматируем данные для отображения в таблице
        formatted_addresses = []
        for addr in created_addresses:
            try:
                # Сохраняем адреса ТОЧНО как в БД, без изменений
                # Это гарантирует сохранение оригинальных почтовых индексов из файла
                address_from_db = addr.address1 if addr.address1 else addr.address
                formatted_addresses.append({
                    "id": addr.id,
                    "address": address_from_db,
                    "address1": address_from_db,  # Используем один и тот же адрес
                    "lat": float(addr.lat),
                    "lon": float(addr.lon),
                    "client_level": addr.client_level or "Standart",
                    "type": "VIP" if addr.client_level and addr.client_level.lower() == "vip" else "Стандарт"
                })
                print(f"📋 [upload] Адрес из БД (id: {addr.id}): {address_from_db[:50]}...")
            except Exception as e:
                print(f"Ошибка форматирования адреса {addr.id}: {e}")
                continue
        
        print(f"Форматировано адресов для отображения: {len(formatted_addresses)}")
        
        return {
            "message": "Файл успешно загружен",
            "file_id": file_id,
            "records_processed": len(created_addresses),
            "total_processed": len(processed_data),
            "errors_count": errors_count,
            "created_addresses": formatted_addresses,
            "file_info": file_info,
            "address": address,
            "period": period,
            "lat": float(lat) if lat else None,
            "lon": float(lon) if lon else None
        }
        
    except Exception as e:
        # Удаляем файл в случае ошибки
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(status_code=500, detail=f"Ошибка обработки файла: {str(e)}")

def process_csv_file(file_path):
    """Обрабатывает CSV файл с клиентами"""
    processed = []
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            for row in reader:
                # Нормализуем данные из CSV
                if 'address' in row and 'lat' in row and 'lon' in row:
                    processed.append({
                        'address': row['address'],
                        'address1': row.get('address1', ''),
                        'lat': float(row['lat']),
                        'lon': float(row['lon']),
                        'client_level': row.get('client_level', 'Standart')
                    })
    except Exception as e:
        raise Exception(f"Ошибка обработки CSV: {e}")
    return processed

def process_json_file(file_path):
    """Обрабатывает JSON файл с клиентами"""
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            data = json.load(file)
            if isinstance(data, list):
                return data
            else:
                return [data]
    except Exception as e:
        raise Exception(f"Ошибка обработки JSON: {e}")

def process_excel_file(file_path):
    """Обрабатывает Excel файл с клиентами (.xlsx, .xls)"""
    try:
        import pandas as pd
        
        # Определяем расширение файла для выбора правильного engine
        file_extension = os.path.splitext(file_path)[1].lower()
        
        # Читаем Excel файл с правильным engine
        try:
            if file_extension == '.xlsx':
                # Для .xlsx файлов используем openpyxl engine
                df = pd.read_excel(file_path, engine='openpyxl')
            elif file_extension == '.xls':
                # Для .xls файлов пробуем разные варианты
                try:
                    # Сначала пробуем xlrd (если установлен)
                    df = pd.read_excel(file_path, engine='xlrd')
                except Exception:
                    # Если xlrd не установлен, пробуем openpyxl (может работать для некоторых .xls)
                    try:
                        print("Попытка чтения .xls файла через openpyxl...")
                        df = pd.read_excel(file_path, engine='openpyxl')
                    except Exception as e2:
                        raise Exception(f"Не удалось прочитать .xls файл. Для .xls файлов рекомендуется установить библиотеку xlrd: pip install xlrd. Ошибка: {e2}")
            else:
                # По умолчанию пробуем автоматически определить
                df = pd.read_excel(file_path, engine='openpyxl')
        except Exception as e:
            raise Exception(f"Не удалось прочитать Excel файл. Для .xlsx файлов нужна библиотека openpyxl, для .xls - xlrd. Установите: pip install openpyxl xlrd. Ошибка: {e}")
        
        print(f"Прочитано строк из Excel: {len(df)}, колонок: {len(df.columns)}")
        print(f"Колонки в файле: {list(df.columns)}")
        
        processed = []
        for i, row in df.iterrows():
            try:
                # Пытаемся найти нужные колонки (поддерживаем разные варианты названий)
                address = None
                for col in ['Адрес объекта', 'Адрес', 'address', 'address1', 'Адрес1', 'Address']:
                    if col in row.index and pd.notna(row[col]) and str(row[col]).strip():
                        address = str(row[col]).strip()
                        break
                
                lat = None
                for col in ['Географическая широта', 'Широта', 'lat', 'latitude', 'Lat', 'LAT', 'Latitude']:
                    if col in row.index and pd.notna(row[col]) and str(row[col]).strip():
                        try:
                            lat = float(str(row[col]).strip())
                            break
                        except (ValueError, TypeError):
                            continue
                
                lon = None
                for col in ['Географическая долгота', 'Долгота', 'lon', 'longitude', 'Lon', 'LON', 'Longitude']:
                    if col in row.index and pd.notna(row[col]) and str(row[col]).strip():
                        try:
                            lon = float(str(row[col]).strip())
                            break
                        except (ValueError, TypeError):
                            continue
                
                client_level = 'Standart'
                for col in ['Уровень клиента', 'Тип', 'client_level', 'Client Level', 'VIP', 'Уровень']:
                    if col in row.index and pd.notna(row[col]) and str(row[col]).strip():
                        level = str(row[col]).strip()
                        if level.upper() in ['VIP', 'ВИП']:
                            client_level = 'VIP'
                        else:
                            client_level = 'Standart'
                        break
                
                # Проверяем обязательные поля
                if not address:
                    print(f"Пропущена строка {i+1}: отсутствует адрес")
                    continue
                if lat is None or lon is None:
                    print(f"Пропущена строка {i+1}: отсутствуют координаты (lat={lat}, lon={lon})")
                    continue
                
                processed.append({
                    'address': address,
                    'address1': address,
                    'lat': lat,
                    'lon': lon,
                    'client_level': client_level
                })
            except Exception as e:
                print(f"Ошибка обработки строки {i+1}: {e}")
                continue
        
        if not processed:
            raise Exception("Не удалось обработать ни одной строки из Excel файла. Проверьте формат данных и наличие колонок: Адрес, Широта, Долгота")
        
        print(f"Обработано строк из Excel: {len(processed)}")
        return processed
    except Exception as e:
        print(f"Ошибка обработки Excel файла: {e}")
        raise Exception(f"Ошибка обработки Excel: {e}")

# ===== ЭНДПОИНТЫ ДЛЯ МАРШРУТИЗАЦИИ =====

@app.get("/api/route")
async def get_route(
    address: Optional[str] = None,
    period: Optional[str] = None,
    lat: Optional[float] = None,
    lon: Optional[float] = None,
    user_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """Получение маршрута на основе загруженных адресов пользователя"""
    db_manager = DatabaseManager(db)
    
    # Определяем user_id (по умолчанию 1)
    if user_id is None:
        user_id = 1
    else:
        try:
            user_id = int(user_id)
        except (ValueError, TypeError):
            user_id = 1
    
    # Получаем все адреса пользователя
    addresses = db_manager.get_addresses_by_user(user_id)
    
    if not addresses:
        raise HTTPException(
            status_code=404, 
            detail=f"Адреса для пользователя {user_id} не найдены. Сначала загрузите файл с адресами."
        )
    
    # Определяем начальную точку
    start_lat = lat
    start_lon = lon
    
    # Если координаты не указаны, пытаемся извлечь их из адреса
    if start_lat is None or start_lon is None:
        if address:
            # Пытаемся извлечь координаты из строки "lat: X, lon: Y"
            import re
            match = re.search(r'lat:\s*([\d.]+).*lon:\s*([\d.]+)', address)
            if match:
                start_lat = float(match.group(1))
                start_lon = float(match.group(2))
        
        # Если все еще не определены, используем первый адрес как начальную точку
        if start_lat is None or start_lon is None:
            if addresses:
                start_lat = float(addresses[0].lat)
                start_lon = float(addresses[0].lon)
            else:
                raise HTTPException(
                    status_code=400, 
                    detail="Не указаны координаты начальной точки (lat, lon) или адрес"
                )
    
    # Определяем конечную точку (по умолчанию - None, чтобы не добавлять конечную точку)
    # Если конечная точка совпадает с начальной, не добавляем её
    end_lat = None
    end_lon = None
    
    # Генерируем маршрут (AI или базовый)
    # Используем AI алгоритм по умолчанию
    waypoints = generate_ai_route(
        start_lat=start_lat,
        start_lon=start_lon,
        client_addresses=addresses,
        end_lat=end_lat,
        end_lon=end_lon
    )
    
    # Рассчитываем общее расстояние и время
    total_distance = calculate_total_distance(waypoints)
    total_time = calculate_total_time(total_distance)
    
    # Формируем ответ в формате, который ожидает фронтенд
    # Преобразуем waypoints в формат для TomTom
    tomtom_waypoints = []
    for wp in waypoints:
        if wp["type"] == "client":
            tomtom_waypoints.append({
                "lat": wp["lat"],
                "lon": wp["lon"],
                "address": wp["address"],
                "level": wp.get("client_level", "Standart")
            })
    
    # Генерируем упрощенный маршрут для отображения
    # (В реальном приложении здесь нужно вызывать TomTom Routing API)
    route_id = str(uuid.uuid4())
    
    # Формируем ответ в формате, который ожидает фронтенд
    return {
        "route_id": route_id,
        "total_distance": total_distance,
        "total_time": total_time,
        "routes": [{
            "day": 1,
            "waypoints": waypoints,
            "tomtom_routes": [{
                "geometry": {
                    "coordinates": [[wp["lon"], wp["lat"]] for wp in waypoints]
                }
            }]
        }],
        "optimized": True
    }

@app.post("/api/route", response_model=RouteResponse)
async def get_ai_route(route_request: RouteRequest, db: Session = Depends(get_db)):
    """Получение оптимального (AI) маршрута"""
    if route_request.algorithm != "ai":
        raise HTTPException(status_code=400, detail="Этот эндпоинт только для AI маршрутов")
    
    # Получаем адреса клиентов из базы данных
    db_manager = DatabaseManager(db)
    client_addresses = []
    for client_id in route_request.client_ids:
        client = db_manager.get_address_by_id(client_id)
        if not client:
            raise HTTPException(status_code=404, detail=f"Клиент с ID {client_id} не найден")
        client_addresses.append(client)
    
    # Генерируем AI маршрут
    route_id = str(uuid.uuid4())
    waypoints = generate_ai_route(
        start_lat=route_request.start_lat,
        start_lon=route_request.start_lon,
        client_addresses=client_addresses,
        end_lat=route_request.end_lat,
        end_lon=route_request.end_lon
    )
    
    # Рассчитываем общее расстояние и время
    total_distance = calculate_total_distance(waypoints)
    total_time = calculate_total_time(total_distance)
    
    # Сохраняем маршрут в базу данных
    route_data = {
        "route_id": route_id,
        "route_type": "ai",
        "total_distance": total_distance,
        "total_time": total_time,
        "waypoints": waypoints
    }
    db_manager.create_route(route_data)
    
    return RouteResponse(
        route_id=route_id,
        total_distance=total_distance,
        total_time=total_time,
        waypoints=waypoints,
        optimized=True
    )

@app.post("/api/route/base", response_model=RouteResponse)
async def get_base_route(route_request: RouteRequest, db: Session = Depends(get_db)):
    """Получение базового маршрута"""
    if route_request.algorithm != "base":
        raise HTTPException(status_code=400, detail="Этот эндпоинт только для базовых маршрутов")
    
    # Получаем адреса клиентов из базы данных
    db_manager = DatabaseManager(db)
    client_addresses = []
    for client_id in route_request.client_ids:
        client = db_manager.get_address_by_id(client_id)
        if not client:
            raise HTTPException(status_code=404, detail=f"Клиент с ID {client_id} не найден")
        client_addresses.append(client)
    
    # Генерируем базовый маршрут
    route_id = str(uuid.uuid4())
    waypoints = generate_base_route(
        start_lat=route_request.start_lat,
        start_lon=route_request.start_lon,
        client_addresses=client_addresses,
        end_lat=route_request.end_lat,
        end_lon=route_request.end_lon
    )
    
    # Рассчитываем общее расстояние и время
    total_distance = calculate_total_distance(waypoints)
    total_time = calculate_total_time(total_distance)
    
    # Сохраняем маршрут в базу данных
    route_data = {
        "route_id": route_id,
        "route_type": "base",
        "total_distance": total_distance,
        "total_time": total_time,
        "waypoints": waypoints
    }
    db_manager.create_route(route_data)
    
    return RouteResponse(
        route_id=route_id,
        total_distance=total_distance,
        total_time=total_time,
        waypoints=waypoints,
        optimized=False
    )

def generate_ai_route(start_lat, start_lon, client_addresses, end_lat=None, end_lon=None):
    """Генерирует AI-оптимизированный маршрут"""
    import math
    
    waypoints = []
    
    # Начальная точка
    waypoints.append({
        "order": 0,
        "type": "start",
        "lat": start_lat,
        "lon": start_lon,
        "address": "Начальная точка",
        "client_id": None
    })
    
    # Сортируем клиентов по расстоянию от начальной точки (упрощенный AI алгоритм)
    sorted_clients = sorted(client_addresses, key=lambda x: 
        math.sqrt((x.lat - start_lat)**2 + (x.lon - start_lon)**2))
    
    # Добавляем клиентов в маршрут
    # ВАЖНО: Используем адреса ТОЧНО из БД, без изменений
    for i, client in enumerate(sorted_clients):
        # Берем адрес напрямую из БД (address1 или address)
        client_address = client.address1 if client.address1 else client.address
        waypoints.append({
            "order": i + 1,
            "type": "client",
            "lat": client.lat,
            "lon": client.lon,
            "address": client_address,  # Адрес из БД
            "address1": client_address,  # Адрес из БД (дублируем для совместимости)
            "client_id": client.id,
            "client_level": client.client_level
        })
        print(f"📍 [generate_ai_route] Добавлен клиент (id: {client.id}): {client_address[:50]}...")
    
    # Конечная точка
    if end_lat and end_lon:
        waypoints.append({
            "order": len(waypoints),
            "type": "end",
            "lat": end_lat,
            "lon": end_lon,
            "address": "Конечная точка",
            "client_id": None
        })
    
    return waypoints

def generate_base_route(start_lat, start_lon, client_addresses, end_lat=None, end_lon=None):
    """Генерирует базовый маршрут (простой порядок)"""
    waypoints = []
    
    # Начальная точка
    waypoints.append({
        "order": 0,
        "type": "start",
        "lat": start_lat,
        "lon": start_lon,
        "address": "Начальная точка",
        "client_id": None
    })
    
    # Добавляем клиентов в том порядке, как они пришли
    # ВАЖНО: Используем адреса ТОЧНО из БД, без изменений
    for i, client in enumerate(client_addresses):
        # Берем адрес напрямую из БД (address1 или address)
        client_address = client.address1 if client.address1 else client.address
        waypoints.append({
            "order": i + 1,
            "type": "client",
            "lat": client.lat,
            "lon": client.lon,
            "address": client_address,  # Адрес из БД
            "address1": client_address,  # Адрес из БД (дублируем для совместимости)
            "client_id": client.id,
            "client_level": client.client_level
        })
        print(f"📍 [generate_base_route] Добавлен клиент (id: {client.id}): {client_address[:50]}...")
    
    # Конечная точка
    if end_lat and end_lon:
        waypoints.append({
            "order": len(waypoints),
            "type": "end",
            "lat": end_lat,
            "lon": end_lon,
            "address": "Конечная точка",
            "client_id": None
        })
    
    return waypoints

def calculate_total_distance(waypoints):
    """Рассчитывает общее расстояние маршрута в км"""
    import math
    
    total_distance = 0
    for i in range(len(waypoints) - 1):
        lat1, lon1 = waypoints[i]["lat"], waypoints[i]["lon"]
        lat2, lon2 = waypoints[i + 1]["lat"], waypoints[i + 1]["lon"]
        
        # Формула гаверсинуса для расчета расстояния
        R = 6371  # Радиус Земли в км
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = (math.sin(dlat/2) * math.sin(dlat/2) + 
             math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * 
             math.sin(dlon/2) * math.sin(dlon/2))
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        distance = R * c
        total_distance += distance
    
    return round(total_distance, 2)

def calculate_total_time(distance_km):
    """Рассчитывает примерное время в пути в часах"""
    # Предполагаем среднюю скорость 30 км/ч в городе
    return round(distance_km / 30, 2)

# ===== ЭНДПОИНТЫ ДЛЯ УПРАВЛЕНИЯ ПОСЕЩЕНИЯМИ =====

@app.post("/api/client/status")
async def update_client_status(status_update: ClientStatusUpdate, db: Session = Depends(get_db)):
    """Отметка посещения клиента"""
    # Проверяем, существует ли клиент
    db_manager = DatabaseManager(db)
    client = db_manager.get_address_by_id(status_update.client_id)
    if not client:
        raise HTTPException(status_code=404, detail=f"Клиент с ID {status_update.client_id} не найден")
    
    # Создаем запись о посещении
    visit_data = {
        "client_id": status_update.client_id,
        "visited": status_update.visited,
        "visit_time": datetime.fromisoformat(status_update.visit_time) if status_update.visit_time else datetime.now(),
        "notes": status_update.notes
    }
    
    visit_record = db_manager.create_visit(visit_data)
    
    return {
        "message": "Статус клиента обновлен",
        "visit_record": {
            "client_id": visit_record.client_id,
            "visited": visit_record.visited,
            "visit_time": visit_record.visit_time.isoformat() if visit_record.visit_time else None,
            "notes": visit_record.notes,
            "timestamp": visit_record.timestamp.isoformat()
        }
    }

# ===== ЭНДПОИНТЫ ДЛЯ ЭКСПОРТА =====

@app.get("/api/export")
async def export_report(
    format: str = "json",
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    client_levels: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Выгрузка итогового отчёта"""
    db_manager = DatabaseManager(db)
    
    # Получаем данные о посещениях с адресами
    export_data = db_manager.get_visits_with_addresses(
        date_from=date_from,
        date_to=date_to,
        client_levels=client_levels
    )
    
    if format.lower() == "csv":
        # Создаем CSV файл
        filename = f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        filepath = f"exports/{filename}"
        os.makedirs("exports", exist_ok=True)
        
        with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
            if export_data:
                fieldnames = export_data[0].keys()
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(export_data)
        
        return FileResponse(
            path=filepath,
            filename=filename,
            media_type='text/csv'
        )
    
    elif format.lower() == "json":
        # Возвращаем JSON
        return {
            "export_info": {
                "format": "json",
                "total_records": len(export_data),
                "date_from": date_from,
                "date_to": date_to,
                "client_levels": client_levels,
                "export_time": datetime.now().isoformat()
            },
            "data": export_data
        }
    
    else:
        raise HTTPException(status_code=400, detail="Поддерживаются только форматы: json, csv")

# ===== НОВЫЕ ЭНДПОИНТЫ ДЛЯ РАБОТЫ С BUTTON_FOR_FRONT.PY =====

@app.post("/api/upload-advanced")
async def upload_advanced_file(file: UploadFile = File(...)):
    """Расширенная загрузка файлов с поддержкой Excel и полной обработкой"""
    if not file.filename:
        raise HTTPException(status_code=400, detail="Файл не выбран")
    
    # Проверяем расширение файла
    if not file.filename.endswith(('.csv', '.json', '.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="Поддерживаются только файлы CSV, JSON и Excel (.xlsx, .xls)")
    
    # Создаем папку для загруженных файлов
    upload_dir = "uploads"
    os.makedirs(upload_dir, exist_ok=True)
    
    # Генерируем уникальное имя файла
    file_id = str(uuid.uuid4())
    file_extension = os.path.splitext(file.filename)[1]
    file_path = os.path.join(upload_dir, f"{file_id}{file_extension}")
    
    try:
        # Сохраняем файл
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Используем функцию из button_for_front.py для полной обработки
        result = process_client_file_complete(file_path, user_id=1)
        
        # Удаляем временный файл
        if os.path.exists(file_path):
            os.remove(file_path)
        
        if result["success"]:
            return {
                "message": "Файл успешно обработан и загружен в базу данных",
                "file_id": file_id,
                "total_processed": result["total_processed"],
                "total_errors": result["total_errors"],
                "errors": result.get("database_info", {}).get("errors", []),
                "processing_time": datetime.now().isoformat()
            }
        else:
            raise HTTPException(status_code=500, detail=f"Ошибка обработки файла: {result['error']}")
            
    except Exception as e:
        # Удаляем файл в случае ошибки
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(status_code=500, detail=f"Ошибка обработки файла: {str(e)}")

@app.post("/api/register")
async def register_new_user(user_data: UserRegistration):
    """Регистрация нового пользователя"""
    try:
        result = register_user(
            first_name=user_data.first_name,
            last_name=user_data.last_name,
            phone_number=user_data.phone_number,
            password=user_data.password
        )
        
        if result["success"]:
            return {
                "message": result["message"],
                "user_id": result["user_id"],
                "first_name": result["first_name"],
                "last_name": result["last_name"],
                "registration_time": result["registration_time"]
            }
        else:
            raise HTTPException(status_code=400, detail=result["error"])
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка регистрации: {str(e)}")

@app.post("/api/login")
async def login_user(login_data: UserLogin):
    """Авторизация пользователя"""
    try:
        # Находим пользователя по номеру телефона
        user = find_user_by_phone(login_data.phone_number)
        
        if not user:
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        
        # Проверяем пароль (простая проверка хеша)
        import hashlib
        password_hash = hashlib.sha256(login_data.password.encode('utf-8')).hexdigest()
        
        if user["password_hash"] != password_hash:
            raise HTTPException(status_code=401, detail="Неверный пароль")
        
        return {
            "message": "Успешная авторизация",
            "user_id": user["user_id"],
            "first_name": user["first_name"],
            "last_name": user["last_name"],
            "phone_number": user["phone_number"]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка авторизации: {str(e)}")

@app.get("/api/user/{user_id}/locations")
async def get_user_locations(user_id: int):
    """Получение локаций пользователя"""
    try:
        result = get_user_available_locations(user_id)
        
        if result["success"]:
            return {
                "user_id": result["user_id"],
                "total_locations": result["total_locations"],
                "visited_locations": result["visited_locations"],
                "available_locations": result["available_locations"],
                "locations": result["locations"],
                "query_time": result["query_time"]
            }
        else:
            raise HTTPException(status_code=404, detail=result["error"])
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка получения локаций: {str(e)}")

@app.post("/api/location/visit")
async def mark_location_as_visited(visit_data: LocationVisit):
    """Отметка посещения локации"""
    try:
        result = mark_location_visited(visit_data.user_id, visit_data.location_id)
        
        if result["success"]:
            return {
                "message": result["message"],
                "user_id": result["user_id"],
                "location_id": result["location_id"],
                "address": result["address"],
                "is_active": result["is_active"],
                "action_time": result["action_time"]
            }
        else:
            raise HTTPException(status_code=400, detail=result["error"])
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка отметки посещения: {str(e)}")

@app.post("/api/stay-period")
async def set_user_stay_period(stay_data: StayPeriodRequest):
    """Установка периода пребывания пользователя"""
    try:
        result = set_stay_period(stay_data.user_id, stay_data.days)
        
        if result["success"]:
            return {
                "message": result["message"],
                "user_id": result["user_id"],
                "stay_days": result["stay_days"],
                "start_date": result["start_date"],
                "end_date": result["end_date"],
                "expires_in_hours": result["expires_in_hours"]
            }
        else:
            raise HTTPException(status_code=400, detail=result["error"])
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка установки периода: {str(e)}")

@app.get("/api/stay-period/{user_id}")
async def get_user_stay_period(user_id: int):
    """Получение информации о периоде пребывания пользователя"""
    try:
        result = check_stay_period(user_id)
        
        if result["success"]:
            return {
                "user_id": result["user_id"],
                "current_day": result["current_day"],
                "total_days": result["total_days"],
                "days_remaining": result["days_remaining"],
                "start_date": result["start_date"],
                "end_date": result["end_date"],
                "is_active": result["is_active"]
            }
        else:
            return {
                "success": False,
                "error": result["error"],
                "user_id": user_id
            }
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка получения периода: {str(e)}")

@app.delete("/api/user/{user_id}/locations")
async def delete_user_locations_endpoint(user_id: int):
    """Удаление всех локаций пользователя"""
    try:
        from button_for_front import delete_user_locations
        result = delete_user_locations(user_id)
        
        if result["success"]:
            return {
                "success": True,
                "message": result["message"],
                "deleted_count": result["deleted_count"],
                "user_id": result["user_id"],
                "deletion_time": result["deletion_time"]
            }
        else:
            raise HTTPException(status_code=400, detail=result["error"])
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка удаления локаций: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    # Запускаем на порту 8000 (основной порт)
    uvicorn.run(app, host="0.0.0.0", port=8000)
