import serial
import time
import serial.tools.list_ports
from .base import IServo

class ServoController(IServo):
    def __init__(self, port: str | None = None, baudrate: int = 115200, timeout: int = 1):
        """
        Инициализация соединения с Arduino
        
        Args:
            port: COM порт (например, 'COM3' или '/dev/ttyUSB0')
            baudrate: Скорость передачи
            timeout: Таймаут чтения
        """
        if port is None:
            port = self._find_arduino_port()
            
        self.ser = serial.Serial(port, baudrate, timeout=timeout)
        time.sleep(2)  # Ожидание инициализации Arduino
        print(f"Подключено к {port}")
        
        # Читаем приветственное сообщение
        self._read_response()
    
    def _find_arduino_port(self) -> str:
        """Автопоиск порта Arduino"""
        ports = list(serial.tools.list_ports.comports())
        for port in ports:
            if 'Arduino' in port.description or 'CH340' in port.description or 'USB Serial' in port.description:
                print(f"Найден Arduino на порту: {port.device}")
                return port.device
        
        raise Exception("Arduino не найден. Укажите порт вручную.")
    
    def set_angle(self, angle: int) -> bool:
        """
        Установка угла сервопривода
        
        Args:
            angle: угол от 0 до 180 градусов
        """
        if not 0 <= angle <= 180:
            print(f"Ошибка: угол {angle} вне диапазона 0-180")
            return False
        
        command = f"{angle}\n"
        self.ser.write(command.encode())
        
        response = self._read_response()
        print(f"Установлен угол: {angle}° - {response}")
        return True
    
    def _read_response(self) -> str:
        """Чтение ответа от Arduino"""
        try:
            response = self.ser.readline().decode().strip()
            return response
        except:
            return ""

    def close(self):
        """Закрытие соединения"""
        if self.ser and self.ser.is_open:
            self.ser.close()
            print("Соединение с сервоприводом закрыто")

class MockServo(IServo):
    """
    Мок-объект для сервопривода.
    Не требует реального подключения.
    """
    def __init__(self, port: str | None = None, **kwargs):
        print("Инициализирован мок-сервопривод")

    def set_angle(self, angle: int) -> bool:
        if not 0 <= angle <= 180:
            print(f"Ошибка (Мок): угол {angle} вне диапазона 0-180")
            return False
        
        print(f"Мок: Установлен угол: {angle}°")
        # Имитация небольшой задержки
        time.sleep(0.1)
        return True

    def close(self):
        print("Мок-сервопривод 'закрыт'")