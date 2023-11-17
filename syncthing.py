'''
import requests

# url = "http://localhost:8384/rest/events?since=240"
# url = "http://localhost:8384/rest/events?since=927&timeout=2"
url = "http://localhost:8384/rest/events/disk?timeout=2"
apikey = "q2SVbJ4ZRQfEZYpfnAocu5nAmMuJpALg"

headers = {
    "X-API-Key": apikey
}

# Llamada GET a la API de Syncthing con la clave de API
response = requests.get(url, headers=headers)

# Comprueba si la respuesta es exitosa (código 200)
if response.status_code == 200:
    # Extrae la versión del JSON de respuesta
    data = response.json()
    # version = data.get('version', 'Desconocida')
    # print(f'La versión actual de Syncthing es: {version}')
    print(f'{data}')
else:
    print(f'Error al llamar a la API: {response.status_code}')
'''

class MyClass:
    def __init__(self, name, age):
      self.name = name
      self.age = age
      
_class = MyClass('hola', 89)
c = _class
print(_class.name, _class.age)
      
_class = MyClass('hola', 'adios')

print(_class.name, _class.age)
print(c.name, c.age)
