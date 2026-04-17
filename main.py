from mqtt_as import MQTTClient
from mqtt_local import config
import uasyncio as asyncio
import dht, machine, json
import random
import ujson
import machine

CONFIG_FILE = "config.json"

id = ""
for b in machine.unique_id():
    id += "{:02X}".format(b)
print("El ID del dispositivo actual es: {}".format(id))

def guardar_config():
    try:
        with open(CONFIG_FILE, "w") as f:
            ujson.dump({"setpoint": setpoint, "periodo": periodo, "modo": modo, "rele": rele_state}, f)
        print("Configuracion guardada")
    except Exception as e:
        print("No se pudo guardar la configuracion:", e)

def cargar_config():
    global setpoint, periodo, modo, rele_state
    try:
        with open(CONFIG_FILE, "r") as f:
            data = ujson.load(f)
            setpoint = int(data.get("setpoint", 25))
            periodo = int(data.get("periodo", 10))
            modo = int(data.get("modo", 0))
            rele_state = int(data.get("rele", 0))  
        print("Configuracion cargada:", data)
    except Exception as e:
        print("No se encontro configuracion previa. Usando valores por defecto.")
        guardar_config()

# Variables globales
setpoint = 25  
periodo = 10  
modo = 0  # 0 -> Manual y 1 -> Automático
rele_state = 0  # 0 -> Apagado y 1 -> Encendido

cargar_config()

# Configuración de pines
# SENSOR_PIN = 16
RELAY_PIN = 15

# d = dht.DHT11(machine.Pin(SENSOR_PIN))
rele = machine.Pin(RELAY_PIN, machine.Pin.OUT)
led = machine.Pin("LED", machine.Pin.OUT)


def accionar_rele(estado_logico):
    """Placa active-low: 1 = encendido lógico → pin en bajo."""
    rele.value(0 if estado_logico == 1 else 1)


accionar_rele(rele_state)

async def destellar_led():
    for _ in range(5):  
        led.on()
        await asyncio.sleep(0.3)  
        led.off()
        await asyncio.sleep(0.3)  

async def receiver(client):
    global setpoint, periodo, modo, rele_state
    async for topic, msg, retained in client.queue:
        topic = topic.decode()
        msg = msg.decode()
        if topic.endswith("/setpoint"):
            setpoint = int(msg.strip())
            print(f"Nuevo setpoint: {setpoint}°C")
        elif topic.endswith("/periodo"):
            periodo = int(msg.strip())
            print(f"Nuevo periodo: {periodo}s")
        elif topic.endswith("/modo"):
            modo = int(msg.strip())
            print(f"Nuevo modo: {'Automatico' if modo == 1 else 'Manual'}")
        elif topic.endswith("/rele"):
            rele_state = int(msg.strip())
            accionar_rele(rele_state)
            print(f"Relé {'ENCENDIDO' if rele_state else 'APAGADO'}")
        elif topic.endswith("/destello"):
            print("Destello activado")
            asyncio.create_task(destellar_led())
        guardar_config()


async def broker_up(client):
    while True:
        await client.up.wait()
        client.up.clear()
        print("WiFi", "conectado")
        await asyncio.sleep(1)
        base_topic = id
        for sub in ["setpoint", "periodo", "destello", "modo", "rele"]:
            await client.subscribe(f"{base_topic}/{sub}", 1)


async def broker_down(client):
    while True:
        await client.down.wait()
        client.down.clear()
        print("WiFi", "desconectado")
        await asyncio.sleep(1)


async def main(client):
    global rele_state
    await client.connect()
    for coro in (receiver, broker_up, broker_down):
        asyncio.create_task(coro(client))
    await asyncio.sleep(2)
    
    while True:
        try:
            # d.measure()
            # temp = d.temperature()
            # hum = d.humidity()
            # Simulación de sensor 
            temp = random.randint(18, 32)
            hum = random.randint(40, 80)

            if int(modo) == 1:
                deseado = 1 if temp > setpoint else 0
                if deseado != rele_state:
                    print("Relé PRENDIDO" if deseado else "Relé APAGADO")
                rele_state = deseado
                accionar_rele(rele_state)
            
            data = {
                "temperatura": temp,
                "humedad": hum,
                "setpoint": setpoint,
                "periodo": periodo,
                "modo": modo,
                "rele": rele_state
            }
            await client.publish(id, json.dumps(data), qos=1)
            
        except OSError:
            print("Error al leer el sensor")
        
        await asyncio.sleep(periodo)

config.update(
    {
        "queue_len": 4,
        "ssl": True,
    }
)

MQTTClient.DEBUG = True
client = MQTTClient(config)

try:
    asyncio.run(main(client))
finally:
    client.close()
    asyncio.new_event_loop()