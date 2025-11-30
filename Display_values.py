import serial
import struct
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
import time

# ===== CONFIGURAZIONE =====
SERIAL_PORT = 'COM6'  # Modifica con la tua porta
BAUD_RATE = 115200
SENSOR_COUNT = 2
MATRIX_SIZE = 4
TOTAL_INTS = SENSOR_COUNT * MATRIX_SIZE  # 8 interi
BYTES_PER_INT = 4
TOTAL_BYTES = TOTAL_INTS * BYTES_PER_INT  # 32 bytes

# Header di sincronizzazione (deve corrispondere a quello Arduino)
HEADER = b'\xAA\x55\xAA\x55'
HEADER_SIZE = len(HEADER)
PACKET_SIZE = HEADER_SIZE + TOTAL_BYTES  # 4 + 32 = 36 bytes

# Range di distanza dei TOF (in mm)
MIN_DISTANCE = 0
MAX_DISTANCE = 4000

class TOFVisualizer:
    def __init__(self, port, baudrate):
        try:
            self.ser = serial.Serial(port, baudrate, timeout=1)
            print(f"✓ Connesso a {port} @ {baudrate} baud")
            time.sleep(2)
            
            # IMPORTANTE: Svuota tutto il buffer accumulato
            print("🗑️  Svuotamento buffer vecchio...")
            self.ser.reset_input_buffer()
            time.sleep(0.5)
            discarded = self.ser.in_waiting
            if discarded > 0:
                self.ser.read(discarded)
                print(f"   Scartati {discarded} bytes vecchi")
            
            # Aspetta di trovare il primo header valido
            print("🔍 Sincronizzazione con il stream...")
            if self.find_header():
                print("✓ Sincronizzato!\n")
            else:
                print("⚠️  Header non trovato, procedo comunque...\n")
        except serial.SerialException as e:
            print(f"✗ Errore apertura porta seriale: {e}")
            exit(1)
        
        # Setup matplotlib
        self.fig, self.ax = plt.subplots(figsize=(10, 6))
        self.fig.canvas.manager.set_window_title('TOF Depth Camera Visualizer')
        
        # Matrice iniziale
        self.data = np.zeros((SENSOR_COUNT, MATRIX_SIZE))
        
        # Statistiche
        self.packets_received = 0
        self.sync_errors = 0
        self.last_values = None
        
        # Immagine
        self.im = self.ax.imshow(
            self.data, 
            cmap='viridis_r',
            interpolation='nearest',
            vmin=MIN_DISTANCE, 
            vmax=MAX_DISTANCE,
            aspect='auto'
        )
        
        # Colorbar
        cbar = self.fig.colorbar(self.im, ax=self.ax, label='Distanza (mm)')
        
        # Labels
        self.title = self.ax.set_title('TOF Depth Camera - In attesa...', fontsize=14, fontweight='bold')
        self.ax.set_xlabel('Colonna sensore', fontsize=11)
        self.ax.set_ylabel('Sensore #', fontsize=11)
        self.ax.set_xticks(range(MATRIX_SIZE))
        self.ax.set_yticks(range(SENSOR_COUNT))
        self.ax.set_yticklabels([f'TOF {i}' for i in range(SENSOR_COUNT)])
        
        # Mostra valori nelle celle
        self.text_objects = []
        for i in range(SENSOR_COUNT):
            row_texts = []
            for j in range(MATRIX_SIZE):
                text = self.ax.text(j, i, '', ha='center', va='center', 
                                   color='white', fontsize=10, fontweight='bold')
                row_texts.append(text)
            self.text_objects.append(row_texts)
        
        plt.tight_layout()
    
    def find_header(self):
        """Cerca l'header di sincronizzazione nel buffer"""
        buffer = bytearray()
        max_search = 1000  # Massimo bytes da cercare (aumentato)
        
        for _ in range(max_search):
            byte = self.ser.read(1)
            if not byte:
                return None
            
            buffer.append(byte[0])
            
            # Mantieni buffer limitato alla dimensione dell'header
            if len(buffer) > HEADER_SIZE:
                buffer.pop(0)
            
            # Controlla se abbiamo trovato l'header
            if len(buffer) == HEADER_SIZE and bytes(buffer) == HEADER:
                return True
        
        return None
    
    def read_data(self):
        """Legge i dati dalla seriale con sincronizzazione"""
        try:
            # Se ci sono più pacchetti in coda, salta a quello più recente
            while self.ser.in_waiting >= PACKET_SIZE * 2:
                # Salta il pacchetto vecchio
                self.ser.read(PACKET_SIZE)
            
            # Cerca l'header
            if not self.find_header():
                self.sync_errors += 1
                return None
            
            # Leggi i dati dopo l'header
            raw_data = self.ser.read(TOTAL_BYTES)
            
            if len(raw_data) != TOTAL_BYTES:
                self.sync_errors += 1
                return None
            
            # Decodifica
            values = struct.unpack(f'<{TOTAL_INTS}i', raw_data)
            
            # Filtra valori fuori range (possibile errore di trasmissione)
            if any(v < -100 or v > 5000 for v in values):
                self.sync_errors += 1
                return None
            
            matrix = np.array(values).reshape(SENSOR_COUNT, MATRIX_SIZE)
            self.packets_received += 1
            self.last_values = values
            
            return matrix
                
        except Exception as e:
            self.sync_errors += 1
            return None
    
    def update_frame(self, frame):
        """Callback per aggiornamento animazione"""
        new_data = self.read_data()
        
        if new_data is not None:
            self.data = new_data
            
            # Aggiorna titolo con statistiche
            self.title.set_text(f'TOF Depth Camera - Pacchetti: {self.packets_received} | Errori sync: {self.sync_errors}')
            
            # Aggiorna immagine
            self.im.set_data(self.data)
            
            # Aggiorna testi
            for i in range(SENSOR_COUNT):
                for j in range(MATRIX_SIZE):
                    value = int(self.data[i, j])
                    self.text_objects[i][j].set_text(f'{value}')
                    
                    # Cambia colore testo per leggibilità
                    if value < MAX_DISTANCE / 2:
                        self.text_objects[i][j].set_color('white')
                    else:
                        self.text_objects[i][j].set_color('black')
        
        return [self.im, self.title] + [text for row in self.text_objects for text in row]
    
    def run(self):
        """Avvia visualizzazione"""
        ani = FuncAnimation(
            self.fig, 
            self.update_frame, 
            interval=50,  # 50ms = 20 FPS
            blit=True,
            cache_frame_data=False
        )
        
        plt.show()
        
    def close(self):
        """Chiudi connessione seriale"""
        if self.ser.is_open:
            self.ser.close()
            print("✓ Porta seriale chiusa")


if __name__ == '__main__':
    print("=== TOF Depth Camera Visualizer ===")
    print(f"Configurazione:")
    print(f"  - Sensori: {SENSOR_COUNT}")
    print(f"  - Valori per sensore: {MATRIX_SIZE}")
    print(f"  - Header: {HEADER.hex()}")
    print(f"  - Packet size: {PACKET_SIZE} bytes")
    print(f"  - Range: {MIN_DISTANCE}-{MAX_DISTANCE} mm\n")
    
    visualizer = TOFVisualizer(SERIAL_PORT, BAUD_RATE)
    
    try:
        visualizer.run()
    except KeyboardInterrupt:
        print("\n✓ Interruzione utente")
    finally:
        visualizer.close()