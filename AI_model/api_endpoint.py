#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🌐 FastAPI endpoints для системы маршрутизации
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Dict
from unified_route_system import UnifiedRouteSystem, Client, ClientLevel
from time_monitor import UserSettings
import os

app = FastAPI(title="Route Optimization API", version="1.0.0")

# Добавляем CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Разрешаем все домены
    allow_credentials=True,
    allow_methods=["*"],  # Разрешаем все HTTP методы
    allow_headers=["*"],  # Разрешаем все заголовки
)

# Инициализация системы
TOMTOM_API_KEY = os.getenv("TOMTOM_API_KEY", "4Me4kS17IKSfQmvDuIgLpsz9jxAu6tt2")
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
system = UnifiedRouteSystem(tomtom_api_key=TOMTOM_API_KEY, model_path="best_unified_model.pth", bot_token=BOT_TOKEN)

@app.get("/")
async def root():
    """Корневой endpoint"""
    return {
        "message": "Route Optimization API",
        "version": "1.0.0",
        "status": "active"
    }

@app.post("/optimize_routes")
async def optimize_routes(data: Dict = None):
    """Оптимизирует маршруты для клиентов"""
    try:
        # Извлекаем параметры из данных
        clients_data = data.get('clients_data') if data else None
        num_days = data.get('num_days', 3) if data else 3

        # Если клиенты не переданы, используем загруженных из файла
        if clients_data is None or len(clients_data) == 0:
            if not system.clients:
                # Загружаем клиентов из файла
                system.load_clients_from_file("DATA (2).txt")
            clients = system.clients
        else:
            # Преобразование данных клиентов из запроса в объекты Client
            clients = []
            for c_data in clients_data:
                # Обработка client_level
                client_level_str = c_data.get('client_level', 'Стандарт')
                if client_level_str == 'VIP':
                    client_level = ClientLevel.VIP
                else:
                    client_level = ClientLevel.REGULAR

                clients.append(Client(
                    id=c_data.get('id'),
                    address=c_data.get('address'),
                    lat=c_data.get('lat'),
                    lon=c_data.get('lon'),
                    client_level=client_level,
                    work_start=c_data.get('work_start', '09:00'),
                    work_end=c_data.get('work_end', '18:00'),
                    lunch_start=c_data.get('lunch_start', '13:00'),
                    lunch_end=c_data.get('lunch_end', '14:00')
                ))

        # Получение маршрутов
        routes_result = system.get_unified_route(clients, num_days)
        return routes_result

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/optimize_routes_from_location")
async def optimize_routes_from_location(clients_data: List[Dict], num_days: int = 3):
    """Оптимизирует маршруты от местоположения пользователя"""
    try:
        # Преобразование данных клиентов
        clients = []
        for c_data in clients_data:
            clients.append(Client(
                id=c_data.get('id'),
                address=c_data.get('address'),
                lat=c_data.get('lat'),
                lon=c_data.get('lon'),
                client_level=ClientLevel(c_data.get('client_level', 'Стандарт')),
                work_start=c_data.get('work_start', '09:00'),
                work_end=c_data.get('work_end', '18:00'),
                lunch_start=c_data.get('lunch_start', '13:00'),
                lunch_end=c_data.get('lunch_end', '14:00')
            ))

        # Получение маршрутов от местоположения пользователя
        routes_result = system.get_route_from_user_location(clients, num_days)
        return routes_result

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/mark_visited")
async def mark_visited(client_id: int, actual_service_time: float = None):
    """Отмечает клиента как посещенного и пересчитывает маршруты"""
    try:
        result = system.mark_client_visited(client_id, actual_service_time)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/mark_delayed")
async def mark_delayed(client_id: int, delay_minutes: float):
    """Отмечает клиента как задержавшегося и пересчитывает маршруты"""
    try:
        result = system.mark_client_delayed(client_id, delay_minutes)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/mark_early_finish")
async def mark_early_finish(client_id: int, early_minutes: float):
    """Отмечает клиента как освободившегося раньше и пересчитывает маршруты"""
    try:
        result = system.mark_client_early_finish(client_id, early_minutes)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/current_status")
async def get_current_status():
    """Возвращает текущий статус системы"""
    try:
        result = system.get_current_status()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ===== ГЕОЛОКАЦИЯ =====

@app.post("/set_location_gps")
async def set_location_gps(data: Dict):
    """Устанавливает местоположение пользователя по GPS координатам"""
    try:
        latitude = data.get('latitude')
        longitude = data.get('longitude')

        if latitude is None or longitude is None:
            raise HTTPException(status_code=400, detail="latitude and longitude are required")

        result = system.get_location_from_gps(latitude, longitude)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/set_location")
async def set_location(gps_coords: List[float] = None, manual_address: str = None):
    """Универсальный endpoint для установки местоположения"""
    try:
        if gps_coords and len(gps_coords) == 2:
            # GPS координаты
            result = system.get_location_from_gps(gps_coords[0], gps_coords[1])
        elif manual_address:
            # Адрес
            result = system.get_location_from_address(manual_address)
        else:
            # Автоматическое определение
            result = system.set_user_location()

        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/set_location_address")
async def set_location_address(data: Dict):
    """Устанавливает местоположение пользователя по адресу"""
    try:
        address = data.get('address')

        if not address:
            raise HTTPException(status_code=400, detail="address is required")

        result = system.get_location_from_address(address)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/get_user_location")
async def get_user_location():
    """Возвращает текущее местоположение пользователя"""
    try:
        result = system.get_user_location()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/update_location")
async def update_location(latitude: float, longitude: float):
    """Обновляет местоположение пользователя"""
    try:
        result = system.update_user_location(latitude, longitude)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/location_suggestions")
async def get_location_suggestions(query: str, limit: int = 5):
    """Получает предложения адресов для автодополнения"""
    try:
        result = system.get_location_suggestions(query, limit)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/auto_detect_location")
async def auto_detect_location():
    """Автоматически определяет местоположение пользователя"""
    try:
        result = system.set_user_location()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/export_routes")
async def export_routes(route_data: Dict, filename: str = "routes.json"):
    """Экспортирует маршруты в JSON файл"""
    try:
        result = system.export_routes_to_json(route_data, filename)
        return {
            'success': True,
            'filename': result,
            'message': f'Маршруты экспортированы в {result}'
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ===== СИСТЕМА УВЕДОМЛЕНИЙ =====

@app.post("/register_telegram_user")
async def register_telegram_user(chat_id: int, settings: Dict = None):
    """Регистрирует пользователя Telegram в системе уведомлений"""
    try:
        from time_monitor import UserSettings

        # Создаем настройки пользователя
        user_settings = UserSettings(
            chat_id=chat_id,
            notifications_enabled=settings.get('notifications_enabled', True) if settings else True,
            departure_reminder_minutes=settings.get('departure_reminder_minutes', 15) if settings else 15,
            lunch_reminder_minutes=settings.get('lunch_reminder_minutes', 15) if settings else 15,
            delay_threshold_minutes=settings.get('delay_threshold_minutes', 5) if settings else 5,
            traffic_threshold_minutes=settings.get('traffic_threshold_minutes', 10) if settings else 10,
            work_start=settings.get('work_start', '09:00') if settings else '09:00',
            work_end=settings.get('work_end', '18:00') if settings else '18:00',
            lunch_start=settings.get('lunch_start', '13:00') if settings else '13:00',
            lunch_end=settings.get('lunch_end', '14:00') if settings else '14:00',
            timezone=settings.get('timezone', 'Europe/Moscow') if settings else 'Europe/Moscow',
            language=settings.get('language', 'ru') if settings else 'ru'
        )

        system.register_telegram_user(chat_id, user_settings)

        return {
            'success': True,
            'message': f'Пользователь {chat_id} зарегистрирован в системе уведомлений',
            'settings': {
                'chat_id': user_settings.chat_id,
                'notifications_enabled': user_settings.notifications_enabled,
                'departure_reminder_minutes': user_settings.departure_reminder_minutes,
                'lunch_reminder_minutes': user_settings.lunch_reminder_minutes,
                'delay_threshold_minutes': user_settings.delay_threshold_minutes,
                'traffic_threshold_minutes': user_settings.traffic_threshold_minutes,
                'work_start': user_settings.work_start,
                'work_end': user_settings.work_end,
                'lunch_start': user_settings.lunch_start,
                'lunch_end': user_settings.lunch_end,
                'timezone': user_settings.timezone,
                'language': user_settings.language
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/add_route_notifications")
async def add_route_notifications(chat_id: int, route_data: Dict):
    """Добавляет уведомления для маршрута"""
    try:
        system.add_route_notifications(chat_id, route_data)
        return {
            'success': True,
            'message': f'Уведомления для маршрута добавлены для пользователя {chat_id}'
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/add_lunch_reminder")
async def add_lunch_reminder(chat_id: int, lunch_time: str):
    """Добавляет напоминание об обеде"""
    try:
        from datetime import datetime
        lunch_datetime = datetime.strptime(lunch_time, '%H:%M')
        system.add_lunch_reminder(chat_id, lunch_datetime)
        return {
            'success': True,
            'message': f'Напоминание об обеде добавлено для {lunch_time}'
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/add_delay_alert")
async def add_delay_alert(chat_id: int, client_id: int, delay_minutes: int):
    """Добавляет уведомление об опоздании"""
    try:
        system.add_delay_alert(chat_id, client_id, delay_minutes)
        return {
            'success': True,
            'message': f'Уведомление об опоздании добавлено для клиента {client_id}'
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/add_traffic_alert")
async def add_traffic_alert(chat_id: int, route_info: Dict):
    """Добавляет уведомление об изменении трафика"""
    try:
        system.add_traffic_alert(chat_id, route_info)
        return {
            'success': True,
            'message': 'Уведомление об изменении трафика добавлено'
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/notification_status")
async def get_notification_status():
    """Возвращает статус системы уведомлений"""
    try:
        return {
            'success': True,
            'notification_system_enabled': system.notification_system is not None,
            'time_monitor_enabled': system.time_monitor is not None,
            'registered_users': len(system.time_monitor.users) if system.time_monitor else 0,
            'active_triggers': len(system.time_monitor.triggers) if system.time_monitor else 0
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/load_clients")
async def load_clients_from_file(data_file: str = "DATA (2).txt"):
    """Загружает клиентов из файла"""
    try:
        clients = system.load_clients_from_file(data_file)
        return {
            'success': True,
            'clients_count': len(clients),
            'clients': [
                {
                    'id': client.id,
                    'address': client.address,
                    'lat': client.lat,
                    'lon': client.lon,
                    'level': client.client_level.value,
                    'work_start': client.work_start,
                    'work_end': client.work_end,
                    'lunch_start': client.lunch_start,
                    'lunch_end': client.lunch_end
                } for client in clients
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/set_location")
async def set_location(location_data: dict):
    """Устанавливает местоположение пользователя"""
    try:
        gps_coords = location_data.get('gps_coords')
        manual_address = location_data.get('manual_address')
        ip_address = location_data.get('ip_address')

        result = system.set_user_location(
            gps_coords=gps_coords,
            manual_address=manual_address,
            ip_address=ip_address
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/update_location")
async def update_location(location_data: dict):
    """Обновляет местоположение пользователя (например, с карты)"""
    try:
        latitude = location_data.get('latitude')
        longitude = location_data.get('longitude')

        if not latitude or not longitude:
            raise HTTPException(status_code=400, detail="Требуются latitude и longitude")

        result = system.update_user_location(latitude, longitude)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/recalculate_routes")
async def recalculate_routes(clients_data: List[Dict], num_days: int = 3):
    """Пересчитывает маршруты с нового местоположения"""
    try:
        # Преобразование данных клиентов
        clients = []
        for c_data in clients_data:
            clients.append(Client(
                id=c_data.get('id'),
                address=c_data.get('address'),
                lat=c_data.get('lat'),
                lon=c_data.get('lon'),
                client_level=ClientLevel(c_data.get('client_level', 'Стандарт')),
                work_start=c_data.get('work_start', '09:00'),
                work_end=c_data.get('work_end', '18:00'),
                lunch_start=c_data.get('lunch_start', '13:00'),
                lunch_end=c_data.get('lunch_end', '14:00')
            ))

        result = system.recalculate_routes_from_new_location(clients, num_days)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/location_suggestions")
async def get_location_suggestions(q: str, limit: int = 5):
    """Получает предложения адресов для автодополнения"""
    try:
        result = system.get_location_suggestions(q, limit)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/current_location")
async def get_current_location():
    """Возвращает текущее местоположение пользователя"""
    try:
        result = system.get_user_location()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/register_telegram_user")
async def register_telegram_user(user_data: dict):
    """Регистрирует пользователя Telegram в системе уведомлений"""
    try:
        chat_id = user_data.get('chat_id')
        if not chat_id:
            raise HTTPException(status_code=400, detail="Требуется chat_id")

        # Создаем настройки пользователя
        user_settings = UserSettings(
            chat_id=chat_id,
            notifications_enabled=user_data.get('notifications_enabled', True),
            departure_reminder_minutes=user_data.get('departure_reminder_minutes', 15),
            lunch_reminder_minutes=user_data.get('lunch_reminder_minutes', 15),
            delay_threshold_minutes=user_data.get('delay_threshold_minutes', 5),
            traffic_threshold_minutes=user_data.get('traffic_threshold_minutes', 10),
            work_start=user_data.get('work_start', '09:00'),
            work_end=user_data.get('work_end', '18:00'),
            lunch_start=user_data.get('lunch_start', '13:00'),
            lunch_end=user_data.get('lunch_end', '14:00'),
            timezone=user_data.get('timezone', 'Europe/Moscow'),
            language=user_data.get('language', 'ru')
        )

        system.register_telegram_user(chat_id, user_settings)

        return {
            'success': True,
            'message': f'Пользователь {chat_id} зарегистрирован в системе уведомлений'
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/add_route_notifications")
async def add_route_notifications(notification_data: dict):
    """Добавляет уведомления для маршрута"""
    try:
        chat_id = notification_data.get('chat_id')
        route_result = notification_data.get('route_result')

        if not chat_id or not route_result:
            raise HTTPException(status_code=400, detail="Требуются chat_id и route_result")

        system.add_route_notifications(chat_id, route_result)

        return {
            'success': True,
            'message': f'Уведомления добавлены для пользователя {chat_id}'
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/check_delays")
async def check_delays(delay_data: dict):
    """Проверяет опоздания и добавляет уведомления"""
    try:
        chat_id = delay_data.get('chat_id')
        current_time = delay_data.get('current_time')

        if not chat_id:
            raise HTTPException(status_code=400, detail="Требуется chat_id")

        system.check_delays(chat_id, current_time)

        return {
            'success': True,
            'message': f'Проверка опозданий выполнена для пользователя {chat_id}'
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/check_traffic_changes")
async def check_traffic_changes(traffic_data: dict):
    """Проверяет изменения трафика и добавляет уведомления"""
    try:
        chat_id = traffic_data.get('chat_id')
        old_route_time = traffic_data.get('old_route_time')
        new_route_time = traffic_data.get('new_route_time')

        if not chat_id or old_route_time is None or new_route_time is None:
            raise HTTPException(status_code=400, detail="Требуются chat_id, old_route_time и new_route_time")

        system.check_traffic_changes(chat_id, old_route_time, new_route_time)

        return {
            'success': True,
            'message': f'Проверка изменений трафика выполнена для пользователя {chat_id}'
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/notification_status")
async def get_notification_status(chat_id: int):
    """Возвращает статус уведомлений пользователя"""
    try:
        if not system.time_monitor:
            return {
                'success': False,
                'message': 'Система уведомлений не инициализирована'
            }

        user_triggers = system.time_monitor.get_user_triggers(chat_id)
        monitor_status = system.time_monitor.get_status()

        return {
            'success': True,
            'chat_id': chat_id,
            'active_triggers': len(user_triggers),
            'monitoring_active': monitor_status['monitoring'],
            'triggers': [
                {
                    'type': trigger.trigger_type.value,
                    'time': trigger.trigger_time.isoformat(),
                    'message': trigger.message
                }
                for trigger in user_triggers
            ]
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    """Проверка состояния системы"""
    return {
        "status": "healthy",
        "tomtom_api_key": "configured" if TOMTOM_API_KEY else "missing",
        "bot_token": "configured" if BOT_TOKEN != "YOUR_BOT_TOKEN_HERE" else "missing",
        "model_loaded": "best_unified_model.pth" if os.path.exists("best_unified_model.pth") else "not_found",
        "notifications_enabled": system.notification_system is not None,
        "time_monitoring": system.time_monitor.monitoring if system.time_monitor else False
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

# Для запуска: uvicorn api_endpoint:app --reload
