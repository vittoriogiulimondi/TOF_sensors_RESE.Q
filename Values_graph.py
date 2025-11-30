import serial
import struct
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from collections import deque
import time

# ===== CONFIGURAZIONE =====
SERIAL_PORT = 'COM6'  # Modifica con la tua porta
BAUD_RATE = 115200
SENSOR_COUNT = 2
MATRIX_SIZE = 4
TOTAL_INTS = SENSOR_COUNT * MATRIX_SIZE
BYTES_PER_INT = 4
TOTAL_BYTES = TOTAL_INTS * BYTES_PER_INT

# Header di sincronizzazione
HEADER = b'\xAA\x55\xAA\x55'
HEADER_SIZE = len(HEADER)

# Configurazione grafico
MAX_POINTS = 200  # Numero di campioni visualizzati (ultimi N secondi * 10)
SENSOR_TO_PLOT = 0  # Quale sensore visualizzare (0 o 1)

class TOFStabilityMonitor:
    def __init__(self, port, baudrate):
        try:
            self.ser = serial.Serial(port, baudrate, timeout=1)
            print(f"✓ Connesso a {port} @ {baudrate} baud")
            time.sleep(2)
            
            # Svuota buffer vecchio
            print("🗑️  Svuotamento buffer...")
            self.ser.reset_input_buffer()
            time.sleep(0.5)
            discarded = self.ser.in_waiting
            if discarded > 0:
                self.ser.read(discarded)
            
            print("🔍 Sincronizzazione...")
            if self.find_header():
                print("✓ Sincronizzato!\n")
            
        except serial.SerialException as e:
            print(f"✗ Errore: {e}")
            exit(1)
        
        # Buffers per i dati (uno per ogni canale del sensore)
        self.time_data = deque(maxlen=MAX_POINTS)
        self.sensor_data = [deque(maxlen=MAX_POINTS) for _ in range(MATRIX_SIZE)]
        
        self.start_time = time.time()
        self.packets_received = 0
        self.sync_errors = 0
        
        # Setup matplotlib
        self.fig, (self.ax1, self.ax2) = plt.subplots(2, 1, figsize=(12, 8))
        self.fig.canvas.manager.set_window_title('TOF Stability Monitor')
        
        # Grafico principale - tutte le colonne del sensore
        self.lines = []
        colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#FFA07A']
        for i in range(MATRIX_SIZE):
            line, = self.ax1.plot([], [], 'o-', label=f'Colonna {i}', 
                                 color=colors[i], linewidth=2, markersize=4, alpha=0.8)
            self.lines.append(line)
        
        self.ax1.set_xlabel('Tempo (s)', fontsize=11)
        self.ax1.set_ylabel('Distanza (mm)', fontsize=11)
        self.ax1.set_title(f'TOF {SENSOR_TO_PLOT} - Stabilità nel tempo', 
                          fontsize=13, fontweight='bold')
        self.ax1.legend(loc='upper right')
        self.ax1.grid(True, alpha=0.3)
        self.ax1.set_ylim(0, 2500)
        
        # Grafico statistiche - deviazione standard
        self.std_bars = self.ax2.bar(range(MATRIX_SIZE), [0]*MATRIX_SIZE, 
                                     color=colors, alpha=0.7, edgecolor='black')
        self.ax2.set_xlabel('Colonna sensore', fontsize=11)
        self.ax2.set_ylabel('Deviazione Standard (mm)', fontsize=11)
        self.ax2.set_title('Stabilità per colonna (minore = più stabile)', 
                          fontsize=13, fontweight='bold')
        self.ax2.set_xticks(range(MATRIX_SIZE))
        self.ax2.set_xticklabels([f'Col {i}' for i in range(MATRIX_SIZE)])
        self.ax2.grid(True, alpha=0.3, axis='y')
        self.ax2.set_ylim(0, 50)  # Max 50mm di deviazione
        
        # Testo per statistiche
        self.stats_text = self.ax2.text(0.02, 0.95, '', transform=self.ax2.transAxes,
                                       verticalalignment='top', fontsize=9,
                                       bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
        
        plt.tight_layout()
    
    def find_header(self):
        """Cerca l'header di sincronizzazione"""
        buffer = bytearray()
        for _ in range(1000):
            byte = self.ser.read(1)
            if not byte:
                return None
            buffer.append(byte[0])
            if len(buffer) > HEADER_SIZE:
                buffer.pop(0)
            if len(buffer) == HEADER_SIZE and bytes(buffer) == HEADER:
                return True
        return None
    
    def read_data(self):
        """Legge dati dalla seriale"""
        try:
            # Salta pacchetti vecchi se accumulati
            while self.ser.in_waiting >= (HEADER_SIZE + TOTAL_BYTES) * 2:
                self.ser.read(HEADER_SIZE + TOTAL_BYTES)
            
            if not self.find_header():
                self.sync_errors += 1
                return None
            
            raw_data = self.ser.read(TOTAL_BYTES)
            if len(raw_data) != TOTAL_BYTES:
                self.sync_errors += 1
                return None
            
            values = struct.unpack(f'<{TOTAL_INTS}i', raw_data)
            
            # Filtra valori invalidi
            if any(v < -100 or v > 5000 for v in values):
                self.sync_errors += 1
                return None
            
            matrix = np.array(values).reshape(SENSOR_COUNT, MATRIX_SIZE)
            self.packets_received += 1
            
            return matrix
            
        except Exception as e:
            self.sync_errors += 1
            return None
    
    def update_frame(self, frame):
        """Aggiorna il grafico"""
        new_data = self.read_data()
        
        if new_data is not None:
            # Prendi i dati del sensore selezionato
            sensor_values = new_data[SENSOR_TO_PLOT]
            
            # Aggiungi timestamp
            current_time = time.time() - self.start_time
            self.time_data.append(current_time)
            
            # Aggiungi valori per ogni colonna
            for i in range(MATRIX_SIZE):
                self.sensor_data[i].append(sensor_values[i])
            
            # Aggiorna grafico principale
            if len(self.time_data) > 1:
                times = list(self.time_data)
                for i in range(MATRIX_SIZE):
                    values = list(self.sensor_data[i])
                    self.lines[i].set_data(times, values)
                
                # Auto-scale X axis
                self.ax1.set_xlim(max(0, times[-1] - 20), times[-1] + 1)
                
                # Auto-scale Y axis basato sui dati visibili
                all_visible_values = []
                for i in range(MATRIX_SIZE):
                    all_visible_values.extend(list(self.sensor_data[i]))
                if all_visible_values:
                    #y_min = max(0, min(all_visible_values) - 100)
                    y_min = 0
                    #y_max = max(all_visible_values) + 100
                    y_max = 2000
                    self.ax1.set_ylim(y_min, y_max)
            
            # Calcola e aggiorna statistiche (solo se ci sono abbastanza dati)
            if len(self.time_data) >= 10:
                std_values = []
                mean_values = []
                for i in range(MATRIX_SIZE):
                    data_array = np.array(list(self.sensor_data[i]))
                    std_values.append(np.std(data_array))
                    mean_values.append(np.mean(data_array))
                
                # Aggiorna barre
                for bar, std_val in zip(self.std_bars, std_values):
                    bar.set_height(std_val)
                
                # Auto-scale barre
                max_std = max(std_values) if std_values else 10
                self.ax2.set_ylim(0, max(max_std * 1.2, 10))
                
                # Aggiorna testo statistiche
                stats_text = f"Pacchetti: {self.packets_received} | Errori: {self.sync_errors}\n"
                stats_text += "Medie: " + " | ".join([f"C{i}: {mean_values[i]:.1f}mm" for i in range(MATRIX_SIZE)])
                self.stats_text.set_text(stats_text)
        
        return self.lines + list(self.std_bars) + [self.stats_text]
    
    def run(self):
        """Avvia visualizzazione"""
        ani = FuncAnimation(
            self.fig,
            self.update_frame,
            interval=100,  # 100ms = 10 FPS
            blit=True,
            cache_frame_data=False
        )
        plt.show()
    
    def close(self):
        """Chiudi connessione"""
        if self.ser.is_open:
            self.ser.close()
            print("✓ Porta seriale chiusa")


if __name__ == '__main__':
    print("=== TOF Stability Monitor ===")
    print(f"Monitoraggio TOF #{SENSOR_TO_PLOT}")
    print(f"Campioni visualizzati: {MAX_POINTS}")
    print(f"Finestra temporale: ~{MAX_POINTS/10:.0f} secondi\n")
    
    monitor = TOFStabilityMonitor(SERIAL_PORT, BAUD_RATE)
    
    try:
        monitor.run()
    except KeyboardInterrupt:
        print("\n✓ Interruzione utente")
        
        # Stampa statistiche finali
        print("\n📊 STATISTICHE FINALI:")
        for i in range(MATRIX_SIZE):
            if len(monitor.sensor_data[i]) > 0:
                data = np.array(list(monitor.sensor_data[i]))
                print(f"  Colonna {i}:")
                print(f"    Media: {np.mean(data):.2f} mm")
                print(f"    Std Dev: {np.std(data):.2f} mm")
                print(f"    Min: {np.min(data):.0f} mm")
                print(f"    Max: {np.max(data):.0f} mm")
    finally:
        monitor.close()