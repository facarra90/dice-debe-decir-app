}import csv

def read_conversion_factors():
    """
    Lee el archivo "factores_conversion.csv" y procesa sus datos para crear
    un diccionario anidado con la siguiente estructura:
    
    {
        año_base_1: {año_destino_1: factor, año_destino_2: factor, ...},
        año_base_2: {año_destino_1: factor, año_destino_2: factor, ...},
        ...
    }
    
    Requerimientos:
      1. Apertura del Archivo:
         - Se abre el archivo "factores_conversion.csv" utilizando open() con newline=''
           y encoding="latin-1" para manejar correctamente los saltos de línea y caracteres especiales.
      2. Uso de csv.reader:
         - Se crea un objeto lector con csv.reader y se establece el delimitador en tabulación (delimiter="\t").
      3. Procesamiento de la Cabecera:
         - Se lee la primera línea con next(reader). Se asume que el primer elemento es una etiqueta
           (por ejemplo, "Año Base") y los elementos restantes representan los años destino.
         - Se convierten los encabezados (a partir del segundo elemento) a enteros, eliminando espacios.
      4. Iteración sobre las Filas:
         - Para cada fila se extrae el primer elemento, que representa el año base, y se convierte a entero.
         - Se inicializa un diccionario para ese año base.
         - Se itera sobre el resto de las celdas (usando enumerate para obtener el índice) y, para cada celda:
           - Se eliminan espacios en blanco y se reemplazan comas por puntos.
           - Se intenta convertir el valor a float; si la conversión falla, se asigna None.
           - Se asocia el valor convertido al año destino correspondiente, obtenido de la cabecera.
    """
    conversion_factors = {}
    
    # Abrir el archivo "factores_conversion.csv" con newline='' y encoding="latin-1"
    with open("factores_conversion.csv", newline='', encoding="latin-1") as csvfile:
        # Crear un objeto lector con delimitador de tabulación
        reader = csv.reader(csvfile, delimiter="\t")
        
        # Leer la cabecera: el primer elemento es una etiqueta y los demás son años destino
        header = next(reader)
        # Convertir los encabezados (a partir del segundo elemento) a enteros, eliminando espacios en blanco
        target_years = [int(col.strip()) for col in header[1:]]
        
        # Iterar sobre cada fila del archivo
        for row in reader:
            # Omitir filas vacías
            if not row:
                continue
            
            # Extraer y convertir el año base (primer elemento) a entero
            try:
                base_year = int(row[0].strip())
            except ValueError:
                # Si no se puede convertir, omitir esta fila
                continue
            
            # Inicializar un diccionario para este año base
            factors_for_base = {}
            
            # Iterar sobre las celdas restantes utilizando enumerate para obtener el índice
            for i, cell in enumerate(row[1:]):
                # Eliminar espacios en blanco y reemplazar comas por puntos
                cell_clean = cell.strip().replace(',', '.')
                try:
                    # Intentar convertir el valor a float
                    factor = float(cell_clean)
                except ValueError:
                    # Si la conversión falla, asignar None
                    factor = None
                
                # Asociar el valor convertido al año de destino correspondiente
                target_year = target_years[i]
                factors_for_base[target_year] = factor
            
            # Asignar el diccionario de factores para este año base al diccionario global
            conversion_factors[base_year] = factors_for_base
    
    return conversion_factors

# Ejemplo de uso:
if __name__ == "__main__":
    factors = read_conversion_factors()
    print(factors)
