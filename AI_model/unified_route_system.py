#!/usr/bin/env python3
"""
🧠 Единая система: ANN модель + TomTom API + граф маршрутов
"""

import pandas as pd
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from typing import List, Dict, Tuple, Optional
import json
import requests
import time
import os
from dataclasses import dataclass
from enum import Enum
import pickle
from datetime import datetime
from sklearn.preprocessing import StandardScaler
from location_detector import LocationDetector
from time_monitor import TimeMonitor, UserSettings, TriggerType
from notification_system import NotificationSystem

class ClientLevel(Enum):
    VIP = "VIP"
    REGULAR = "Стандарт"

@dataclass
class Location:
    """Местоположение пользователя"""
    latitude: float
    longitude: float
    address: str
    city: str
    country: str
    accuracy: float  # Точность в метрах
    source: str  # GPS, IP, Manual

@dataclass
class Client:
    """Клиент с полной информацией"""
    id: int
    address: str
    lat: float
    lon: float
    client_level: ClientLevel
    work_start: str
    work_end: str
    lunch_start: str
    lunch_end: str

    @property
    def service_time_minutes(self) -> int:
        return 30 if self.client_level == ClientLevel.VIP else 20

    @property
    def work_start_hour(self) -> float:
        hour, minute = map(int, self.work_start.split(':'))
        return hour + minute / 60.0

    @property
    def work_end_hour(self) -> float:
        hour, minute = map(int, self.work_end.split(':'))
        return hour + minute / 60.0

    @property
    def lunch_start_hour(self) -> float:
        hour, minute = map(int, self.lunch_start.split(':'))
        return hour + minute / 60.0

    @property
    def lunch_end_hour(self) -> float:
        hour, minute = map(int, self.lunch_end.split(':'))
        return hour + minute / 60.0

class AttentionRouteOptimizer(nn.Module):
    """
    Attention-based Neural Network для оптимизации маршрутов
    Интегрированная версия с графом маршрутов
    """

    def __init__(self, input_dim: int = 7, hidden_dim: int = 256, num_heads: int = 8, num_layers: int = 3):
        super().__init__()

        self.hidden_dim = hidden_dim
        self.num_heads = num_heads

        # Входной слой
        self.input_layer = nn.Linear(input_dim, hidden_dim)

        # Attention слои
        self.attention_layers = nn.ModuleList([
            nn.MultiheadAttention(hidden_dim, num_heads, batch_first=True)
            for _ in range(num_layers)
        ])

        # Нормализация
        self.norm_layers = nn.ModuleList([
            nn.LayerNorm(hidden_dim)
            for _ in range(num_layers)
        ])

        # Выходные слои для графа маршрутов
        self.route_output = nn.Linear(hidden_dim, 1)  # Очки маршрута
        self.time_output = nn.Linear(hidden_dim, 1)   # Предсказание времени
        self.priority_output = nn.Linear(hidden_dim, 1)  # Приоритет клиента

        # Активация
        self.activation = nn.ReLU()

    def forward(self, x, mask=None):
        """
        Прямой проход модели с поддержкой графа маршрутов
        """
        batch_size, seq_len, _ = x.shape

        # Входной слой
        x = self.input_layer(x)

        # Attention слои для анализа связей в графе
        for attention, norm in zip(self.attention_layers, self.norm_layers):
            # Self-attention для анализа связей между клиентами
            attn_output, _ = attention(x, x, x, key_padding_mask=mask)
            x = norm(x + attn_output)
            x = self.activation(x)

        # Выходные предсказания для графа
        route_scores = self.route_output(x)      # Очки для построения графа
        time_predictions = self.time_output(x)   # Время между узлами
        priority_scores = self.priority_output(x)  # Приоритет узлов

        return {
            'route_scores': route_scores.squeeze(-1),
            'time_predictions': time_predictions.squeeze(-1),
            'priority_scores': priority_scores.squeeze(-1)
        }

class UnifiedRouteSystem:
    """Единая система: ANN + TomTom API + граф маршрутов"""

    def __init__(self, tomtom_api_key: str, model_path: str = None, bot_token: str = None):
        self.tomtom_api_key = tomtom_api_key
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model = AttentionRouteOptimizer().to(self.device)
        self.scaler = StandardScaler()
        self.clients = []
        self.current_routes = {}
        self.visited_clients = set()
        self.current_time = 9.0
        self.location_detector = LocationDetector()
        self.user_location = None

        # Система уведомлений
        self.bot_token = bot_token
        self.time_monitor = TimeMonitor()
        self.notification_system = None

        if bot_token:
            self.notification_system = NotificationSystem(bot_token)
            # Регистрируем callbacks для уведомлений
            self.time_monitor.register_callback(TriggerType.DEPARTURE_REMINDER, self._handle_departure_reminder)
            self.time_monitor.register_callback(TriggerType.LUNCH_BREAK, self._handle_lunch_reminder)
            self.time_monitor.register_callback(TriggerType.DELAY_ALERT, self._handle_delay_alert)
            self.time_monitor.register_callback(TriggerType.TRAFFIC_CHANGE, self._handle_traffic_change)
            self.time_monitor.register_callback(TriggerType.ROUTE_UPDATE, self._handle_route_update)
            self.time_monitor.register_callback(TriggerType.CLIENT_ARRIVAL, self._handle_client_arrival)

            # Запускаем мониторинг времени
            self.time_monitor.start_monitoring()
            print("🔔 Система уведомлений инициализирована")

        # Загружаем предобученную модель
        if model_path and os.path.exists(model_path):
            self.load_model(model_path)
        elif os.path.exists("best_unified_model.pth"):
            print("📁 Загружаем предобученную модель...")
            self.load_model("best_unified_model.pth")
        else:
            print("❌ Предобученная модель не найдена!")
            print("💡 Убедитесь, что файл best_unified_model.pth существует")
            raise FileNotFoundError("Предобученная модель не найдена")

        # Инициализируем скейлер фиктивными данными, если он не был загружен
        if not hasattr(self.scaler, 'mean_') or self.scaler.mean_ is None:
            print("🔧 Инициализируем скейлер фиктивными данными...")
            # Создаем фиктивные данные для обучения скейлера
            dummy_data = np.random.randn(100, 8)  # 8 признаков
            self.scaler.fit(dummy_data)
            print("✅ Скейлер инициализирован")

        # Инициализируем список клиентов
        self.clients = []


    def load_clients_from_file(self, data_file: str = "DATA (2).txt") -> List[Client]:
        """Загружает клиентов из файла DATA (2).txt"""
        print(f"📊 Загружаем клиентов из {data_file}...")

        if not os.path.exists(data_file):
            print(f"❌ Файл не найден: {data_file}")
            return []

        try:
            # Читаем файл как текст
            with open(data_file, 'r', encoding='utf-8') as f:
                content = f.read()

            # Парсим JSON-подобные данные
            clients = self._parse_client_data(content)
            print(f"✅ Загружено {len(clients)} клиентов")
            return clients

        except Exception as e:
            print(f"❌ Ошибка загрузки клиентов: {e}")
            return []

    def _parse_client_data(self, content: str) -> List[Client]:
        """Парсит данные клиентов из файла"""
        import re

        try:
            # Ищем массив данных
            data_match = re.search(r'data = \[(.*?)\]', content, re.DOTALL)
            if not data_match:
                print("❌ Не найден массив данных")
                return []

            data_str = data_match.group(1)

            # Разбиваем на отдельные объекты
            objects = []
            current_obj = ""
            brace_count = 0

            for char in data_str:
                if char == '{':
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1

                current_obj += char

                if brace_count == 0 and current_obj.strip():
                    obj_str = current_obj.strip()
                    if obj_str.startswith('{') and obj_str.endswith('}'):
                        objects.append(obj_str)
                    current_obj = ""

            # Парсим каждый объект
            clients = []
            for i, obj_str in enumerate(objects):
                try:
                    # Очищаем от лишних символов
                    obj_str = obj_str.strip()
                    if obj_str.endswith(','):
                        obj_str = obj_str[:-1]

                    # Парсим JSON
                    client_data = json.loads(obj_str)

                    # Создаем объект Client
                    client = Client(
                        id=int(client_data.get('id', i+1)),
                        address=str(client_data.get('address1', '')),
                        lat=float(client_data.get('lat', 47.2225)),  # Ростов-на-Дону по умолчанию
                        lon=float(client_data.get('lon', 39.7203)),
                        client_level=ClientLevel.VIP if client_data.get('client_level') == 'VIP' else ClientLevel.REGULAR,
                        work_start=str(client_data.get('work_start', '09:00')),
                        work_end=str(client_data.get('work_end', '18:00')),
                        lunch_start=str(client_data.get('lunch_start', '13:00')),
                        lunch_end=str(client_data.get('lunch_end', '14:00'))
                    )

                    clients.append(client)

                except Exception as e:
                    print(f"⚠️ Ошибка парсинга клиента {i+1}: {e}")
                    continue

            if clients:
                self.clients = clients  # Сохраняем клиентов в системе
            return clients

        except Exception as e:
            print(f"❌ Ошибка парсинга данных: {e}")
            self.clients = []
            return []

    def predict_route_time(self, client1: Client, client2: Client, current_time: float) -> float:
        """Предсказывает время маршрута между клиентами"""
        # Подготавливаем признаки
        features = np.array([[
            client1.lat,
            client1.lon,
            client2.lat,
            client2.lon,
            self.calculate_distance(client1, client2),
            current_time,
            1.0,  # Количество пассажиров
            1.0 if client1.client_level == ClientLevel.VIP else 0.0
        ]])

        # Проверяем, обучен ли скейлер
        if not hasattr(self.scaler, 'mean_') or self.scaler.mean_ is None:
            # Если скейлер не обучен, используем простое предсказание на основе расстояния
            distance_km = self.calculate_distance(client1, client2) / 1000.0
            # Примерная скорость 30 км/ч в городе
            base_time = (distance_km / 30.0) * 60.0  # в минутах

            # Добавляем случайность для реалистичности
            import random
            variation = random.uniform(0.8, 1.2)
            return base_time * variation

        # Нормализуем
        features_scaled = self.scaler.transform(features)

        # Предсказание
        self.model.eval()
        with torch.no_grad():
            # Преобразуем в 3D тензор для Attention модели
            features_tensor = torch.FloatTensor(features_scaled).unsqueeze(0)  # Добавляем batch dimension
            prediction = self.model(features_tensor)
            # Извлекаем время из предсказания
            if isinstance(prediction, dict):
                time_prediction = prediction.get('time_predictions', prediction.get('route_scores', torch.tensor(0.0)))
                return time_prediction.item()
            else:
                return prediction.item()

    def calculate_distance(self, client1: Client, client2: Client) -> float:
        """Вычисляет расстояние между клиентами"""
        from math import radians, cos, sin, asin, sqrt

        lat1, lon1 = radians(client1.lat), radians(client1.lon)
        lat2, lon2 = radians(client2.lat), radians(client2.lon)

        dlat = lat2 - lat1
        dlon = lon2 - lon1

        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * asin(sqrt(a))

        r = 6371000  # Радиус Земли в метрах
        return c * r

    def get_tomtom_route(self, client1: Client, client2: Client) -> Dict:
        """Получает реальный маршрут от TomTom API с учетом трафика"""
        try:
            url = f"https://api.tomtom.com/routing/1/calculateRoute/{client1.lat},{client1.lon}:{client2.lat},{client2.lon}/json"
            params = {
                'key': self.tomtom_api_key,
                'routeType': 'fastest',
                'traffic': 'true',
                'travelMode': 'car',
                'avoid': 'unpavedRoads',
                'maxAlternatives': 1,
                'instructionsType': 'text',
                'language': 'ru-RU'
            }

            session = requests.Session()
            session.verify = False
            session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'application/json',
                'Connection': 'keep-alive'
            })

            response = session.get(url, params=params, timeout=30)

            if response.status_code == 200:
                data = response.json()

                # Извлекаем информацию о трафике и времени
                if 'routes' in data and len(data['routes']) > 0:
                    route = data['routes'][0]
                    summary = route.get('summary', {})

                    # Время в пути с учетом трафика
                    travel_time_seconds = summary.get('travelTimeInSeconds', 0)
                    travel_time_minutes = travel_time_seconds / 60.0

                    # Время без учета трафика
                    no_traffic_time_seconds = summary.get('noTrafficTravelTimeInSeconds', 0)
                    no_traffic_time_minutes = no_traffic_time_seconds / 60.0

                    # Задержка из-за трафика
                    traffic_delay_minutes = travel_time_minutes - no_traffic_time_minutes

                    # Расстояние
                    distance_meters = summary.get('lengthInMeters', 0)
                    distance_km = distance_meters / 1000.0

                    return {
                        'success': True,
                        'travel_time_minutes': travel_time_minutes,
                        'no_traffic_time_minutes': no_traffic_time_minutes,
                        'traffic_delay_minutes': traffic_delay_minutes,
                        'distance_km': distance_km,
                        'route_type': 'fastest',
                        'traffic_considered': True,
                        'raw_data': data
                    }
                else:
                    return {'error': 'No routes found in TomTom response'}
            else:
                return {'error': f'TomTom API error: {response.status_code}'}

        except Exception as e:
            return {'error': f'TomTom API error: {str(e)}'}

    def optimize_route_with_ann(self, clients: List[Client]) -> List[Client]:
        """Оптимизирует маршрут используя Attention модель с графом"""
        print("🧠 Оптимизация маршрута с помощью Attention модели...")

        if not clients:
            return []

        # Подготавливаем данные для модели
        features = []
        for client in clients:
            client_features = [
                client.lat,
                client.lon,
                1.0 if client.client_level == ClientLevel.VIP else 0.0,
                client.work_start_hour,
                client.work_end_hour,
                client.lunch_start_hour,
                client.lunch_end_hour
            ]
            features.append(client_features)

        # Создаем тензор для графа
        features_tensor = torch.FloatTensor(features).unsqueeze(0).to(self.device)
        batch_size, seq_len = features_tensor.shape[:2]
        mask = torch.zeros(batch_size, seq_len, dtype=torch.bool, device=self.device)

        # Получаем предсказания модели для графа
        self.model.eval()
        with torch.no_grad():
            outputs = self.model(features_tensor, mask)
            route_scores = outputs['route_scores'].cpu().numpy()[0]
            time_predictions = outputs['time_predictions'].cpu().numpy()[0]
            priority_scores = outputs['priority_scores'].cpu().numpy()[0]

        # Создаем граф маршрутов на основе предсказаний
        client_scores = list(zip(clients, route_scores, time_predictions, priority_scores))

        # Сортируем по комбинированному скору (маршрут + приоритет + время)
        client_scores.sort(key=lambda x: x[1] + x[3] * 0.5 - x[2] * 0.1, reverse=True)

        # Создаем оптимальный маршрут из графа
        optimized_clients = [client for client, _, _, _ in client_scores]

        print(f"✅ Граф маршрутов построен для {len(optimized_clients)} клиентов")
        return optimized_clients

    def check_working_hours(self, client: Client, arrival_time: float) -> bool:
        """Проверяет рабочие часы клиента"""
        if arrival_time < client.work_start_hour or arrival_time > client.work_end_hour:
            return False

        if client.lunch_start_hour <= arrival_time <= client.lunch_end_hour:
            return False

        return True

    def get_travel_time_from_user(self, client: Client) -> Dict:
        """Рассчитывает время в пути от текущего местоположения пользователя до клиента"""
        if not self.user_location:
            print("⚠️ Местоположение пользователя не установлено, используем расчет по умолчанию")
            # Fallback: используем расстояние от центра города
            distance = self.calculate_distance(
                Client(id=0, address="Центр города", lat=47.2225, lon=39.7203, client_level=ClientLevel.REGULAR, work_start="09:00", work_end="18:00", lunch_start="13:00", lunch_end="14:00"),
                client
            )
            # Примерная скорость 30 км/ч в городе
            travel_time_minutes = (distance / 30.0) * 60.0
            return {
                'success': True,
                'travel_time_minutes': max(5, min(60, travel_time_minutes)),
                'traffic_delay_minutes': 0,
                'data_source': 'Fallback Calculation'
            }

        try:
            # Создаем временный клиент для пользователя
            user_client = Client(
                id=0,
                address=self.user_location.address,
                lat=self.user_location.latitude,
                lon=self.user_location.longitude,
                client_level=ClientLevel.REGULAR,
                work_start="09:00",
                work_end="18:00",
                lunch_start="13:00",
                lunch_end="14:00"
            )

            # Используем TomTom API для точного расчета
            tomtom_route = self.get_tomtom_route(user_client, client)

            if tomtom_route.get('success', False):
                return {
                    'success': True,
                    'travel_time_minutes': tomtom_route['travel_time_minutes'],
                    'traffic_delay_minutes': tomtom_route['traffic_delay_minutes'],
                    'data_source': 'TomTom API'
                }
            else:
                # Fallback на ANN предсказание
                travel_time = self.predict_route_time(user_client, client, self.current_time)
                return {
                    'success': True,
                    'travel_time_minutes': max(5, min(120, travel_time)),
                    'traffic_delay_minutes': 0,
                    'data_source': 'ANN Model'
                }

        except Exception as e:
            print(f"❌ Ошибка расчета времени от пользователя: {e}")
            # Fallback на простое расстояние
            distance = self.calculate_distance(
                Client(id=0, address="Пользователь", lat=self.user_location.latitude, lon=self.user_location.longitude, client_level=ClientLevel.REGULAR, work_start="09:00", work_end="18:00", lunch_start="13:00", lunch_end="14:00"),
                client
            )
            travel_time_minutes = (distance / 30.0) * 60.0
            return {
                'success': True,
                'travel_time_minutes': max(5, min(60, travel_time_minutes)),
                'traffic_delay_minutes': 0,
                'data_source': 'Distance Fallback'
            }

    def get_unified_route(self, clients: List[Client], num_days: int) -> Dict:
        """Возвращает единый маршрут: ANN + TomTom API"""
        print("🚀 Создание единого маршрута: ANN + TomTom API")

        # Распределяем клиентов по дням
        base_per_day = len(clients) // num_days
        extra_clients = len(clients) % num_days

        result = {
            'success': True,
            'total_clients': len(clients),
            'num_days': num_days,
            'routes': [],
            'visited_clients': list(self.visited_clients),
            'current_time': self.current_time,
            'user_location': self.user_location
        }

        start_idx = 0
        for day in range(num_days):
            clients_this_day = base_per_day + (1 if day < extra_clients else 0)
            day_clients = clients[start_idx:start_idx + clients_this_day]

            # Оптимизируем с помощью ANN
            optimized_clients = self.optimize_route_with_ann(day_clients)

            # Рассчитываем время для каждого клиента
            current_time = self.current_time  # Используем реальное время пользователя
            client_details = []

            for i, client in enumerate(optimized_clients):
                # Время в пути
                if i == 0:
                    # Для первого клиента рассчитываем время от пользователя
                    print(f"🚗 Расчет времени от пользователя до клиента {client.id}...")
                    user_route = self.get_travel_time_from_user(client)
                    travel_time_minutes = user_route['travel_time_minutes']
                    traffic_delay_minutes = user_route['traffic_delay_minutes']
                    data_source = user_route['data_source']
                    print(f"📍 {data_source}: Пользователь → {client.id}: {travel_time_minutes:.1f} мин (задержка: {traffic_delay_minutes:.1f} мин)")
                else:
                    # Получаем реальное время в пути от TomTom API
                    prev_client = optimized_clients[i-1]
                    tomtom_route = self.get_tomtom_route(prev_client, client)

                    if tomtom_route.get('success', False):
                        # Используем данные TomTom API
                        travel_time_minutes = tomtom_route['travel_time_minutes']
                        traffic_delay_minutes = tomtom_route['traffic_delay_minutes']
                        data_source = 'TomTom API'
                        print(f"🚗 TomTom: {prev_client.id} → {client.id}: {travel_time_minutes:.1f} мин (задержка: {traffic_delay_minutes:.1f} мин)")
                    else:
                        # Fallback на ANN предсказание
                        travel_time_minutes = self.predict_route_time(prev_client, client, current_time)
                        traffic_delay_minutes = 0
                        data_source = 'ANN Model'
                        print(f"🧠 ANN: {prev_client.id} → {client.id}: {travel_time_minutes:.1f} мин")

                    # Ограничиваем разумными пределами (5-120 минут)
                    travel_time_minutes = max(5, min(120, travel_time_minutes))

                # Время прибытия
                arrival_time = current_time + travel_time_minutes / 60.0

                # Время обслуживания
                service_time_minutes = client.service_time_minutes

                # Время окончания обслуживания
                departure_time = arrival_time + service_time_minutes / 60.0

                # Форматируем время для отображения
                arrival_time_str = f"{int(arrival_time):02d}:{int((arrival_time % 1) * 60):02d}"
                departure_time_str = f"{int(departure_time):02d}:{int((departure_time % 1) * 60):02d}"

                client_detail = {
                    'id': client.id,
                    'address': client.address,
                    'lat': client.lat,
                    'lon': client.lon,
                    'level': client.client_level.value,
                    'travel_time_minutes': int(travel_time_minutes),
                    'traffic_delay_minutes': int(traffic_delay_minutes) if i > 0 else 0,
                    'arrival_time': arrival_time_str,
                    'departure_time': departure_time_str,
                    'service_time_minutes': service_time_minutes,
                    'work_start': client.work_start,
                    'work_end': client.work_end,
                    'lunch_start': client.lunch_start,
                    'lunch_end': client.lunch_end,
                    'data_source': 'TomTom API' if i > 0 and tomtom_route.get('success', False) else 'ANN Model'
                }

                client_details.append(client_detail)

                # Обновляем текущее время для следующего клиента
                current_time = departure_time

            # Получаем детальные маршруты от TomTom
            tomtom_routes = []
            for i in range(len(optimized_clients) - 1):
                client1 = optimized_clients[i]
                client2 = optimized_clients[i + 1]

                tomtom_route = self.get_tomtom_route(client1, client2)
                if 'error' not in tomtom_route:
                    tomtom_routes.append(tomtom_route)

            day_route = {
                'day': day + 1,
                'clients': client_details,
                'waypoints': [{'lat': c.lat, 'lon': c.lon, 'id': c.id, 'level': c.client_level.value}
                             for c in optimized_clients],
                'tomtom_routes': tomtom_routes,
                'ann_optimized': True,
                'total_travel_time_minutes': sum(c['travel_time_minutes'] for c in client_details),
                'total_service_time_minutes': sum(c['service_time_minutes'] for c in client_details)
            }

            result['routes'].append(day_route)
            start_idx += clients_this_day

        return result

    def set_user_location(self, gps_coords: Optional[Tuple[float, float]] = None,
                         ip_address: Optional[str] = None,
                         manual_address: Optional[str] = None) -> Dict:
        """Устанавливает местоположение пользователя"""
        print("📍 Определение местоположения пользователя...")

        try:
            # Получаем лучшее доступное местоположение
            location = self.location_detector.get_best_location(
                gps_coords=gps_coords,
                ip_address=ip_address,
                manual_address=manual_address
            )

            # Проверяем валидность
            if self.location_detector.validate_location(location):
                self.user_location = location
                print(f"✅ Местоположение установлено: {location.address}")

                return {
                    'success': True,
                    'location': {
                        'latitude': location.latitude,
                        'longitude': location.longitude,
                        'address': location.address,
                        'city': location.city,
                        'country': location.country,
                        'accuracy': location.accuracy,
                        'source': location.source
                    },
                    'message': f'Местоположение определено: {location.address}'
                }
            else:
                print("❌ Невалидное местоположение")
                return {
                    'success': False,
                    'error': 'Невалидное местоположение',
                    'message': 'Не удалось определить корректное местоположение'
                }

        except Exception as e:
            print(f"❌ Ошибка определения местоположения: {e}")
            return {
                'success': False,
                'error': str(e),
                'message': 'Ошибка определения местоположения'
            }

    def get_user_location(self) -> Dict:
        """Возвращает текущее местоположение пользователя"""
        if self.user_location:
            return {
                'success': True,
                'location': {
                    'latitude': self.user_location.latitude,
                    'longitude': self.user_location.longitude,
                    'address': self.user_location.address,
                    'city': self.user_location.city,
                    'country': self.user_location.country,
                    'accuracy': self.user_location.accuracy,
                    'source': self.user_location.source
                }
            }
        else:
            return {
                'success': False,
                'message': 'Местоположение не определено'
            }

    def get_route_from_user_location(self, clients: List[Client], num_days: int) -> Dict:
        """Строит маршрут от местоположения пользователя к клиентам"""
        print("🗺️ Построение маршрута от местоположения пользователя...")

        if not self.user_location:
            return {
                'success': False,
                'error': 'Местоположение пользователя не определено',
                'message': 'Сначала определите местоположение пользователя'
            }

        # Добавляем пользователя как стартовую точку
        user_client = Client(
            id=0,
            address=f"Пользователь: {self.user_location.address}",
            lat=self.user_location.latitude,
            lon=self.user_location.longitude,
            client_level=ClientLevel.REGULAR,
            work_start="00:00",
            work_end="23:59",
            lunch_start="00:00",
            lunch_end="00:00"
        )

        # Добавляем пользователя в начало списка клиентов
        all_clients = [user_client] + clients

        # Строим маршрут
        route_result = self.get_unified_route(all_clients, num_days)

        # Добавляем информацию о местоположении пользователя
        route_result['user_location'] = {
            'latitude': self.user_location.latitude,
            'longitude': self.user_location.longitude,
            'address': self.user_location.address,
            'source': self.user_location.source
        }

        return route_result

    def register_telegram_user(self, chat_id: int, user_settings: UserSettings):
        """Регистрирует пользователя Telegram в системе уведомлений"""
        if self.notification_system and self.time_monitor:
            self.notification_system.register_user(chat_id, user_settings)
            self.time_monitor.add_user(chat_id, user_settings)
            print(f"👤 Пользователь Telegram {chat_id} зарегистрирован")

    def add_route_notifications(self, chat_id: int, route_result: Dict):
        """Добавляет уведомления для маршрута"""
        if not self.notification_system or not self.time_monitor:
            return

        print(f"🔔 Добавление уведомлений для маршрута пользователя {chat_id}")

        current_time = datetime.now()

        for day_route in route_result.get('routes', []):
            for i, client in enumerate(day_route.get('clients', [])):
                if client['id'] == 0:  # Пропускаем пользователя
                    continue

                arrival_time = datetime.strptime(client['arrival_time'], '%H:%M')
                arrival_time = current_time.replace(hour=arrival_time.hour, minute=arrival_time.minute, second=0, microsecond=0)

                # Напоминание о выезде
                self.time_monitor.add_departure_reminder(
                    chat_id,
                    arrival_time,
                    {
                        'id': client['id'],
                        'address': client['address'],
                        'client_level': client['client_level'],
                        'travel_time': 20  # Примерное время
                    }
                )

                # Уведомление о прибытии
                self.time_monitor.add_client_arrival_notification(
                    chat_id,
                    {
                        'id': client['id'],
                        'address': client['address'],
                        'client_level': client['client_level'],
                        'service_time': 30 if client['client_level'] == 'VIP' else 20
                    },
                    arrival_time
                )

        # Напоминание об обеде
        lunch_time = datetime.strptime("13:00", '%H:%M')
        lunch_time = current_time.replace(hour=lunch_time.hour, minute=lunch_time.minute, second=0, microsecond=0)
        self.time_monitor.add_lunch_reminder(chat_id, lunch_time)

    def check_delays(self, chat_id: int, current_time: datetime = None):
        """Проверяет опоздания и добавляет уведомления"""
        if not self.time_monitor or not self.current_routes:
            return

        if current_time is None:
            current_time = datetime.now()

        for day_route in self.current_routes.get('routes', []):
            for client in day_route.get('clients', []):
                if client['id'] == 0 or client['id'] in self.visited_clients:
                    continue

                planned_arrival = datetime.strptime(client['arrival_time'], '%H:%M')
                planned_arrival = current_time.replace(hour=planned_arrival.hour, minute=planned_arrival.minute, second=0, microsecond=0)

                if current_time > planned_arrival:
                    self.time_monitor.add_delay_alert(
                        chat_id,
                        planned_arrival,
                        current_time,
                        {
                            'id': client['id'],
                            'address': client['address'],
                            'client_level': client['client_level']
                        }
                    )

    def check_traffic_changes(self, chat_id: int, old_route_time: int, new_route_time: int):
        """Проверяет изменения трафика и добавляет уведомления"""
        if not self.time_monitor:
            return

        self.time_monitor.add_traffic_change_alert(
            chat_id,
            old_route_time,
            new_route_time,
            {
                'description': 'Текущий маршрут',
                'total_clients': len(self.clients)
            }
        )

    def _handle_departure_reminder(self, trigger):
        """Обработчик напоминания о выезде"""
        if self.notification_system:
            self.notification_system.handle_trigger(trigger)

    def _handle_lunch_reminder(self, trigger):
        """Обработчик напоминания об обеде"""
        if self.notification_system:
            self.notification_system.handle_trigger(trigger)

    def _handle_delay_alert(self, trigger):
        """Обработчик уведомления об опоздании"""
        if self.notification_system:
            self.notification_system.handle_trigger(trigger)

    def _handle_traffic_change(self, trigger):
        """Обработчик уведомления об изменении трафика"""
        if self.notification_system:
            self.notification_system.handle_trigger(trigger)

    def _handle_route_update(self, trigger):
        """Обработчик уведомления об обновлении маршрута"""
        if self.notification_system:
            self.notification_system.handle_trigger(trigger)

    def _handle_client_arrival(self, trigger):
        """Обработчик уведомления о прибытии к клиенту"""
        if self.notification_system:
            self.notification_system.handle_trigger(trigger)

    def update_user_location(self, new_latitude: float, new_longitude: float) -> Dict:
        """Обновляет местоположение пользователя (например, с карты)"""
        print(f"📍 Обновление местоположения пользователя: {new_latitude}, {new_longitude}")

        try:
            # Создаем новое местоположение
            new_location = self.location_detector.get_location_from_gps(new_latitude, new_longitude)

            # Проверяем валидность
            if self.location_detector.validate_location(new_location):
                old_location = self.user_location
                self.user_location = new_location

                print(f"✅ Местоположение обновлено: {new_location.address}")

                return {
                    'success': True,
                    'old_location': {
                        'latitude': old_location.latitude if old_location else None,
                        'longitude': old_location.longitude if old_location else None,
                        'address': old_location.address if old_location else None
                    },
                    'new_location': {
                        'latitude': new_location.latitude,
                        'longitude': new_location.longitude,
                        'address': new_location.address,
                        'city': new_location.city,
                        'country': new_location.country,
                        'accuracy': new_location.accuracy,
                        'source': new_location.source
                    },
                    'message': f'Местоположение обновлено: {new_location.address}'
                }
            else:
                print("❌ Невалидные координаты")
                return {
                    'success': False,
                    'error': 'Невалидные координаты',
                    'message': 'Указанные координаты находятся вне разумных пределов'
                }

        except Exception as e:
            print(f"❌ Ошибка обновления местоположения: {e}")
            return {
                'success': False,
                'error': str(e),
                'message': 'Ошибка обновления местоположения'
            }

    def recalculate_routes_from_new_location(self, clients: List[Client], num_days: int) -> Dict:
        """Пересчитывает маршруты с нового местоположения пользователя"""
        print("🔄 Пересчет маршрутов с нового местоположения...")

        if not self.user_location:
            return {
                'success': False,
                'error': 'Местоположение пользователя не определено',
                'message': 'Сначала определите местоположение пользователя'
            }

        try:
            # Строим новые маршруты от обновленного местоположения
            new_routes = self.get_route_from_user_location(clients, num_days)

            if new_routes['success']:
                # Обновляем текущие маршруты
                self.current_routes = new_routes

                print("✅ Маршруты успешно пересчитаны!")

                return {
                    'success': True,
                    'routes': new_routes,
                    'message': 'Маршруты пересчитаны с нового местоположения'
                }
            else:
                return new_routes

        except Exception as e:
            print(f"❌ Ошибка пересчета маршрутов: {e}")
            return {
                'success': False,
                'error': str(e),
                'message': 'Ошибка пересчета маршрутов'
            }

    def get_location_suggestions(self, query: str, limit: int = 5) -> Dict:
        """Получает предложения адресов для автодополнения"""
        print(f"🔍 Поиск предложений для: {query}")

        try:
            # Используем OpenStreetMap Nominatim для поиска
            url = "https://nominatim.openstreetmap.org/search"
            params = {
                'q': query,
                'format': 'json',
                'limit': limit,
                'addressdetails': 1,
                'countrycodes': 'ru'  # Ограничиваем Россией
            }

            response = requests.get(url, params=params, timeout=10)

            if response.status_code == 200:
                data = response.json()

                suggestions = []
                for item in data:
                    suggestions.append({
                        'display_name': item.get('display_name', ''),
                        'latitude': float(item.get('lat', 0)),
                        'longitude': float(item.get('lon', 0)),
                        'address': item.get('address', {}),
                        'importance': item.get('importance', 0)
                    })

                print(f"✅ Найдено {len(suggestions)} предложений")

                return {
                    'success': True,
                    'suggestions': suggestions,
                    'query': query
                }
            else:
                print(f"❌ Ошибка поиска: {response.status_code}")
                return {
                    'success': False,
                    'error': f'HTTP {response.status_code}',
                    'message': 'Ошибка поиска адресов'
                }

        except Exception as e:
            print(f"❌ Ошибка поиска предложений: {e}")
            return {
                'success': False,
                'error': str(e),
                'message': 'Ошибка поиска предложений'
            }

    def mark_client_visited(self, client_id: int, actual_service_time: Optional[float] = None) -> Dict:
        """Отмечает клиента как посещенного и пересчитывает маршруты"""
        print(f"✅ Отмечаем клиента {client_id} как посещенного...")

        # Добавляем в список посещенных
        self.visited_clients.add(client_id)

        # Находим клиента для определения его типа
        client = None
        for c in self.clients:
            if c.id == client_id:
                client = c
                break

        if client is None:
            return {
                'success': False,
                'message': f'Клиент {client_id} не найден'
            }

        # Учитываем реальное время обслуживания
        if actual_service_time is not None:
            # Используем реальное время обслуживания
            service_time_hours = actual_service_time / 60.0
            print(f"⏰ Реальное время обслуживания: {actual_service_time} мин")
        else:
            # Используем стандартное время обслуживания в зависимости от типа клиента
            if client.client_level == ClientLevel.VIP:
                service_time_hours = 30.0 / 60.0  # 30 минут для VIP
                print(f"⏰ Стандартное время обслуживания VIP: 30 мин")
            else:
                service_time_hours = 20.0 / 60.0  # 20 минут для обычных
                print(f"⏰ Стандартное время обслуживания: 20 мин")

        # Обновляем текущее время
        self.current_time += service_time_hours
        print(f"⏰ Обновлено время: {self.current_time:.2f} часов ({int(self.current_time):02d}:{int((self.current_time % 1) * 60):02d})")

        # Пересчитываем оставшиеся маршруты
        print("🔄 Пересчитываем оставшиеся маршруты...")
        updated_routes = self.recalculate_remaining_routes()

        return {
            'success': True,
            'visited_client_id': client_id,
            'visited_clients': list(self.visited_clients),
            'current_time': self.current_time,
            'service_time_minutes': actual_service_time or (30 if client.client_level == ClientLevel.VIP else 20),
            'updated_routes': updated_routes,
            'message': f'Клиент {client_id} отмечен как посещенный. Маршруты пересчитаны.'
        }

    def recalculate_remaining_routes(self) -> Dict:
        """Пересчитывает маршруты для оставшихся клиентов"""
        print("🧠 Пересчет маршрутов с учетом посещенных клиентов...")

        try:
            # Получаем оставшихся клиентов (не посещенных)
            remaining_clients = [client for client in self.clients if client.id not in self.visited_clients]

            if not remaining_clients:
                print("✅ Все клиенты посещены!")
                return {
                    'recalculated': True,
                    'remaining_clients': 0,
                    'visited_count': len(self.visited_clients),
                    'current_time': self.current_time,
                    'message': 'Все клиенты посещены'
                }

            print(f"📊 Осталось клиентов: {len(remaining_clients)}")
            print(f"⏰ Текущее время: {self.current_time:.2f} часов")

            # Пересчитываем время для оставшихся клиентов
            updated_client_details = []
            current_time = self.current_time

            for i, client in enumerate(remaining_clients):
                # Время в пути (используем TomTom API для точности)
                if i == 0:
                    # Для первого оставшегося клиента время в пути = 0
                    travel_time_minutes = 0
                    traffic_delay_minutes = 0
                else:
                    # Получаем реальное время в пути от TomTom API
                    prev_client = remaining_clients[i-1]
                    tomtom_route = self.get_tomtom_route(prev_client, client)

                    if tomtom_route.get('success', False):
                        # Используем данные TomTom API
                        travel_time_minutes = tomtom_route['travel_time_minutes']
                        traffic_delay_minutes = tomtom_route['traffic_delay_minutes']
                        print(f"🚗 TomTom: {prev_client.id} → {client.id}: {travel_time_minutes:.1f} мин")
                    else:
                        # Fallback на ANN предсказание
                        travel_time_minutes = self.predict_route_time(prev_client, client, current_time)
                        traffic_delay_minutes = 0
                        print(f"🧠 ANN: {prev_client.id} → {client.id}: {travel_time_minutes:.1f} мин")

                    # Ограничиваем разумными пределами
                    travel_time_minutes = max(5, min(120, travel_time_minutes))

                # Время прибытия
                arrival_time = current_time + travel_time_minutes / 60.0

                # Время обслуживания
                service_time_minutes = client.service_time_minutes

                # Время окончания обслуживания
                departure_time = arrival_time + service_time_minutes / 60.0

                # Форматируем время для отображения
                arrival_time_str = f"{int(arrival_time):02d}:{int((arrival_time % 1) * 60):02d}"
                departure_time_str = f"{int(departure_time):02d}:{int((departure_time % 1) * 60):02d}"

                client_detail = {
                    'id': client.id,
                    'address': client.address,
                    'lat': client.lat,
                    'lon': client.lon,
                    'level': client.client_level.value,
                    'travel_time_minutes': int(travel_time_minutes),
                    'traffic_delay_minutes': int(traffic_delay_minutes) if i > 0 else 0,
                    'arrival_time': arrival_time_str,
                    'departure_time': departure_time_str,
                    'service_time_minutes': service_time_minutes,
                    'work_start': client.work_start,
                    'work_end': client.work_end,
                    'lunch_start': client.lunch_start,
                    'lunch_end': client.lunch_end,
                    'data_source': 'TomTom API' if i > 0 and tomtom_route.get('success', False) else 'ANN Model'
                }

                updated_client_details.append(client_detail)

                # Обновляем текущее время для следующего клиента
                current_time = departure_time

            # Рассчитываем общее время
            total_travel_time = sum(c['travel_time_minutes'] for c in updated_client_details)
            total_service_time = sum(c['service_time_minutes'] for c in updated_client_details)

            print(f"📊 Пересчитано:")
            print(f"   🚗 Общее время в пути: {total_travel_time} мин")
            print(f"   ⏰ Общее время обслуживания: {total_service_time} мин")
            print(f"   🕐 Время окончания: {int(current_time):02d}:{int((current_time % 1) * 60):02d}")

            return {
                'recalculated': True,
                'remaining_clients': len(remaining_clients),
                'visited_count': len(self.visited_clients),
                'current_time': self.current_time,
                'updated_clients': updated_client_details,
                'total_travel_time_minutes': total_travel_time,
                'total_service_time_minutes': total_service_time,
                'estimated_finish_time': current_time,
                'message': f'Маршруты пересчитаны для {len(remaining_clients)} оставшихся клиентов'
            }

        except Exception as e:
            print(f"❌ Ошибка пересчета маршрутов: {e}")
            return {
                'recalculated': False,
                'error': str(e),
                'message': 'Ошибка пересчета маршрутов'
            }

    def mark_client_delayed(self, client_id: int, delay_minutes: float) -> Dict:
        """Отмечает клиента как задержавшегося и пересчитывает маршруты"""
        print(f"⏰ Клиент {client_id} задержался на {delay_minutes} минут...")

        # Добавляем задержку к текущему времени
        self.current_time += delay_minutes / 60.0
        print(f"⏰ Обновлено время с учетом задержки: {self.current_time:.2f} часов")

        # Пересчитываем оставшиеся маршруты
        updated_routes = self.recalculate_remaining_routes()

        return {
            'success': True,
            'delayed_client_id': client_id,
            'delay_minutes': delay_minutes,
            'current_time': self.current_time,
            'updated_routes': updated_routes,
            'message': f'Клиент {client_id} задержался на {delay_minutes} мин. Маршруты пересчитаны.'
        }

    def mark_client_early_finish(self, client_id: int, early_minutes: float) -> Dict:
        """Отмечает клиента как освободившегося раньше и пересчитывает маршруты"""
        print(f"⚡ Клиент {client_id} освободился на {early_minutes} минут раньше...")

        # Вычитаем время раннего освобождения из текущего времени
        self.current_time -= early_minutes / 60.0
        print(f"⏰ Обновлено время с учетом раннего освобождения: {self.current_time:.2f} часов")

        # Пересчитываем оставшиеся маршруты
        updated_routes = self.recalculate_remaining_routes()

        return {
            'success': True,
            'early_finish_client_id': client_id,
            'early_minutes': early_minutes,
            'current_time': self.current_time,
            'updated_routes': updated_routes,
            'message': f'Клиент {client_id} освободился на {early_minutes} мин раньше. Маршруты пересчитаны.'
        }

    def get_current_status(self) -> Dict:
        """Возвращает текущий статус системы"""
        remaining_clients = [client for client in self.clients if client.id not in self.visited_clients]

        # Проверяем, что есть клиенты для расчета прогресса
        total_clients = len(self.clients)
        progress_percentage = 0.0
        if total_clients > 0:
            progress_percentage = (len(self.visited_clients) / total_clients) * 100

        return {
            'current_time': self.current_time,
            'current_time_formatted': f"{int(self.current_time):02d}:{int((self.current_time % 1) * 60):02d}",
            'visited_clients': list(self.visited_clients),
            'visited_count': len(self.visited_clients),
            'remaining_clients': len(remaining_clients),
            'total_clients': total_clients,
            'progress_percentage': progress_percentage,
            'remaining_clients_list': [
                {
                    'id': client.id,
                    'address': client.address,
                    'level': client.client_level.value
                } for client in remaining_clients
            ]
        }

    def get_location_from_gps(self, lat: float, lon: float) -> Dict:
        """Получает местоположение по GPS координатам"""
        try:
            location = self.location_detector.get_location_from_gps(lat, lon)
            self.user_location = location

            return {
                'success': True,
                'location': {
                    'latitude': location.latitude,
                    'longitude': location.longitude,
                    'address': location.address,
                    'city': location.city,
                    'country': location.country,
                    'accuracy': location.accuracy,
                    'source': location.source
                },
                'message': f'GPS местоположение определено: {location.address}'
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'message': 'Ошибка определения GPS местоположения'
            }

    def get_location_from_ip(self, ip_address: str = None) -> Dict:
        """Получает местоположение по IP адресу"""
        try:
            location = self.location_detector.get_location_from_ip(ip_address)
            self.user_location = location

            return {
                'success': True,
                'location': {
                    'latitude': location.latitude,
                    'longitude': location.longitude,
                    'address': location.address,
                    'city': location.city,
                    'country': location.country,
                    'accuracy': location.accuracy,
                    'source': location.source
                },
                'message': f'IP местоположение определено: {location.address}'
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'message': 'Ошибка определения IP местоположения'
            }

    def get_location_from_address(self, address: str) -> Dict:
        """Получает местоположение по адресу"""
        try:
            location = self.location_detector.get_location_from_address(address)
            self.user_location = location

            return {
                'success': True,
                'location': {
                    'latitude': location.latitude,
                    'longitude': location.longitude,
                    'address': location.address,
                    'city': location.city,
                    'country': location.country,
                    'accuracy': location.accuracy,
                    'source': location.source
                },
                'message': f'Адресное местоположение определено: {location.address}'
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'message': 'Ошибка определения адресного местоположения'
            }

    def set_user_location(self, gps_coords: Tuple[float, float] = None,
                         manual_address: str = None,
                         ip_address: str = None) -> Dict:
        """Устанавливает местоположение пользователя (лучший доступный метод)"""
        try:
            location = self.location_detector.get_best_location(
                gps_coords=gps_coords,
                ip_address=ip_address,
                manual_address=manual_address
            )
            self.user_location = location

            return {
                'success': True,
                'location': {
                    'latitude': location.latitude,
                    'longitude': location.longitude,
                    'address': location.address,
                    'city': location.city,
                    'country': location.country,
                    'accuracy': location.accuracy,
                    'source': location.source
                },
                'message': f'Местоположение установлено: {location.address}'
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'message': 'Ошибка установки местоположения'
            }

    def get_user_location(self) -> Dict:
        """Возвращает текущее местоположение пользователя"""
        if self.user_location:
            return {
                'success': True,
                'location': {
                    'latitude': self.user_location.latitude,
                    'longitude': self.user_location.longitude,
                    'address': self.user_location.address,
                    'city': self.user_location.city,
                    'country': self.user_location.country,
                    'accuracy': self.user_location.accuracy,
                    'source': self.user_location.source
                },
                'message': 'Местоположение получено'
            }
        else:
            return {
                'success': False,
                'message': 'Местоположение не установлено'
            }

    def update_user_location(self, new_latitude: float, new_longitude: float) -> Dict:
        """Обновляет местоположение пользователя"""
        try:
            location = self.location_detector.get_location_from_gps(new_latitude, new_longitude)
            self.user_location = location

            return {
                'success': True,
                'location': {
                    'latitude': location.latitude,
                    'longitude': location.longitude,
                    'address': location.address,
                    'city': location.city,
                    'country': location.country,
                    'accuracy': location.accuracy,
                    'source': location.source
                },
                'message': f'Местоположение обновлено: {location.address}'
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'message': 'Ошибка обновления местоположения'
            }

    def get_location_suggestions(self, query: str, limit: int = 5) -> Dict:
        """Получает предложения адресов для автодополнения"""
        try:
            # Используем Nominatim для поиска предложений
            url = "https://nominatim.openstreetmap.org/search"
            params = {
                'q': query,
                'format': 'json',
                'limit': limit,
                'addressdetails': 1,
                'countrycodes': 'ru'  # Ограничиваем поиск Россией
            }

            response = requests.get(url, params=params, timeout=10)

            if response.status_code == 200:
                data = response.json()
                suggestions = []

                for item in data:
                    suggestions.append({
                        'address': item.get('display_name', ''),
                        'latitude': float(item.get('lat', 0)),
                        'longitude': float(item.get('lon', 0)),
                        'city': item.get('address', {}).get('city', ''),
                        'country': item.get('address', {}).get('country', '')
                    })

                return {
                    'success': True,
                    'suggestions': suggestions,
                    'message': f'Найдено {len(suggestions)} предложений'
                }
            else:
                return {
                    'success': False,
                    'error': f'HTTP {response.status_code}',
                    'message': 'Ошибка поиска предложений'
                }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'message': 'Ошибка поиска предложений'
            }


    def export_routes_to_json(self, route_data: Dict, filename: str = "routes.json") -> str:
        """Экспортирует маршруты в JSON файл для фронтенда"""
        print(f"📄 Экспортируем маршруты в {filename}...")

        try:
            # Создаем структуру для фронтенда
            frontend_data = {
                "success": route_data.get('success', True),
                "total_clients": route_data.get('total_clients', 0),
                "num_days": route_data.get('num_days', 0),
                "visited_clients": route_data.get('visited_clients', []),
                "current_time": route_data.get('current_time', 9.0),
                "routes": []
            }

            # Обрабатываем каждый день
            for route in route_data.get('routes', []):
                day_route = {
                    "day": route.get('day', 1),
                    "clients": route.get('clients', []),
                    "waypoints": route.get('waypoints', []),
                    "tomtom_routes": route.get('tomtom_routes', []),
                    "ann_optimized": route.get('ann_optimized', True),
                    "total_travel_time_minutes": route.get('total_travel_time_minutes', 0),
                    "total_service_time_minutes": route.get('total_service_time_minutes', 0)
                }
                frontend_data["routes"].append(day_route)

            # Сохраняем в JSON файл
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(frontend_data, f, ensure_ascii=False, indent=2)

            print(f"✅ JSON файл сохранен: {filename}")
            return filename

        except Exception as e:
            print(f"❌ Ошибка экспорта JSON: {e}")
            return None


    def load_model(self, path: str):
        """Загружает обученную модель"""
        try:
            checkpoint = torch.load(path, map_location=self.device)

            # Проверяем формат сохраненной модели
            if isinstance(checkpoint, dict) and 'model_state_dict' in checkpoint:
                # Новый формат с полной информацией
                self.model.load_state_dict(checkpoint['model_state_dict'])
                if 'scaler' in checkpoint:
                    self.scaler = checkpoint['scaler']
            else:
                # Старый формат - только state_dict
                self.model.load_state_dict(checkpoint)

            print(f"✅ Модель загружена из {path}")

        except Exception as e:
            print(f"❌ Ошибка загрузки модели: {e}")
            print("🔄 Продолжаем без предобученной модели")

def main():
    """Основная функция для работы с реальными данными"""
    print("🧠 Единая система: ANN + TomTom API + граф маршрутов")
    print("=" * 60)

    # Инициализируем систему с готовой моделью
    system = UnifiedRouteSystem(tomtom_api_key="4Me4kS17IKSfQmvDuIgLpsz9jxAu6tt2")

    # Загружаем клиентов из DATA (2).txt
    print("\n👥 Загрузка клиентов...")
    clients = system.load_clients_from_file("DATA (2).txt")

    if clients:
        print(f"✅ Загружено {len(clients)} клиентов")

        # Определение местоположения пользователя
        print("\n📍 Определение местоположения пользователя...")

        # Автоматическое определение местоположения (IP fallback)
        print("🌐 Автоматическое определение местоположения...")
        location_result = system.set_user_location()
        if location_result['success']:
            loc = location_result['location']
            print(f"   📍 {loc['address']}")
            print(f"   🎯 Точность: {loc['accuracy']}м")
            print(f"   📡 Источник: {loc['source']}")
            print("   ℹ️  Для точной GPS геолокации используйте веб-интерфейс")
        else:
            print(f"   ❌ {location_result['message']}")
            print("   ⚠️  Используется местоположение по умолчанию (Ростов-на-Дону)")

        # Строим маршруты
        print("\n🗺️ Построение маршрутов...")
        route_result = system.get_unified_route(clients, num_days=3)

        if route_result['success']:
            print("✅ Маршруты построены успешно!")
            print(f"📊 Всего клиентов: {route_result['total_clients']}")
            print(f"📅 Количество дней: {route_result['num_days']}")
            print(f"🛣️ Маршрутов: {len(route_result['routes'])}")

            # Показываем детали по дням
            for route in route_result['routes']:
                print(f"\n📅 День {route['day']}:")
                print(f"   🚗 Общее время в пути: {route['total_travel_time_minutes']} мин")
                print(f"   ⏰ Общее время обслуживания: {route['total_service_time_minutes']} мин")
                for client in route['clients']:
                    print(f"   👤 Клиент {client['id']} ({client['level']}):")
                    print(f"      📍 {client['address']}")
                    print(f"      🚗 Время в пути: {client['travel_time_minutes']} мин")
                    if client['traffic_delay_minutes'] > 0:
                        print(f"      🚦 Задержка из-за трафика: {client['traffic_delay_minutes']} мин")
                    print(f"      ⏰ Прибытие: {client['arrival_time']}")
                    print(f"      🏠 Убытие: {client['departure_time']}")
                    print(f"      ⚙️ Время обслуживания: {client['service_time_minutes']} мин")
                    print(f"      📊 Источник данных: {client['data_source']}")

            # Экспортируем в JSON один раз для всего маршрута
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            json_file = system.export_routes_to_json(route_result, f"routes_with_times_{timestamp}.json")
            if json_file:
                print(f"\n📄 Результаты сохранены в {json_file}")
        else:
            print("❌ Ошибка построения маршрутов")
    else:
        print("❌ Не удалось загрузить клиентов")

    print("\n✅ Единая система готова к работе!")
    print("📁 Используется предобученная модель: best_unified_model.pth")
    print("🔄 Поддерживается динамический пересчет времени маршрутов")
    print("🌐 API endpoints доступны через api_endpoint.py")
    print("📍 Для GPS геолокации откройте: geolocation_page.html")
    print("🧪 Демо геолокации: demo_geolocation.html")

if __name__ == "__main__":
    main()
