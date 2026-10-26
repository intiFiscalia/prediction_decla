"""Mapa de desplazamientos entre texto limpio y texto original (plan_trabajo.md §6.1 paso 1;
CLAUDE.md §4.21: "todo procesamiento trabaja sobre copias con desplazamientos de caracteres que
permiten volver al original"). Cualquier mención o entidad extraída de un texto transformado se
proyecta a través de este mapa para citar el fragmento literal de `RELATO` en bronce.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Tramo:
    limpio_inicio: int
    limpio_fin: int
    original_inicio: int
    original_fin: int


@dataclass
class MapaOffsets:
    tramos: list[Tramo] = field(default_factory=list)

    def proyectar(self, inicio: int, fin: int) -> tuple[int, int]:
        """Proyecta el span `[inicio, fin)` de texto limpio a coordenadas del original.

        Si el span cae dentro de un único tramo de longitud igual en ambos lados, interpola
        linealmente (exacto). En cualquier otro caso (el span cruza varios tramos, o un tramo
        cambió de longitud) devuelve el rango original que envuelve toda la evidencia: nunca más
        angosto que lo real, para no citar texto que no estaba ahí.
        """
        cubiertos = [t for t in self.tramos if t.limpio_fin > inicio and t.limpio_inicio < fin]
        if not cubiertos:
            return (inicio, fin)

        if len(cubiertos) == 1:
            tramo = cubiertos[0]
            largo_limpio = tramo.limpio_fin - tramo.limpio_inicio
            largo_original = tramo.original_fin - tramo.original_inicio
            if largo_limpio == largo_original:
                desplazamiento = tramo.original_inicio - tramo.limpio_inicio
                return (inicio + desplazamiento, fin + desplazamiento)

        return (cubiertos[0].original_inicio, cubiertos[-1].original_fin)


def componer(mapa_previo: MapaOffsets, mapa_siguiente: MapaOffsets) -> MapaOffsets:
    """Compone dos mapas de una cadena de transformaciones: si `mapa_previo` va de texto0 a
    texto1 y `mapa_siguiente` va de texto1 a texto2, el resultado va de texto0 a texto2
    directamente (sin pasar por texto1).
    """
    tramos_compuestos = []
    for tramo in mapa_siguiente.tramos:
        original_inicio, original_fin = mapa_previo.proyectar(
            tramo.original_inicio, tramo.original_fin
        )
        tramos_compuestos.append(
            Tramo(tramo.limpio_inicio, tramo.limpio_fin, original_inicio, original_fin)
        )
    return MapaOffsets(tramos=tramos_compuestos)


class ConstructorTextoConOffsets:
    """Ensambla texto limpio fragmento a fragmento, registrando a qué tramo del original
    corresponde cada fragmento agregado. Un fragmento vacío (p. ej. una región eliminada por
    completo) no agrega un tramo, pero los tramos vecinos siguen acotando sus bordes.
    """

    def __init__(self) -> None:
        self._partes: list[str] = []
        self._tramos: list[Tramo] = []
        self._cursor = 0

    def agregar(self, texto: str, original_inicio: int, original_fin: int) -> None:
        if not texto:
            return
        inicio = self._cursor
        self._partes.append(texto)
        self._cursor += len(texto)
        self._tramos.append(Tramo(inicio, self._cursor, original_inicio, original_fin))

    def construir(self) -> tuple[str, MapaOffsets]:
        return "".join(self._partes), MapaOffsets(tramos=self._tramos)
