# Plan: Issue 8 - LLM Client Abstraction & Fake

## 1. Contexto y Objetivos
- **Issue**: [8 - LLM client abstraction & fake](https://github.com/ale-camer/autonomous-trading-analyst/issues/8)
- **Milestone**: M2 - ReAct Agent Core
- **Objetivo**: Crear una abstracción (`LLMClient`) independiente del proveedor (OpenAI, Anthropic, etc.) que normalice los mensajes, llamadas a herramientas (tools) y conteo de tokens. Además, desarrollar un `FakeLLMClient` que permita programar respuestas predefinidas para realizar tests unitarios y deterministas del ciclo ReAct del agente, sin incurrir en costos ni depender de APIs externas.

## 2. Diseño de Componentes

### 2.1 Modelos de Mensajes (`src/autonomous_trading_analyst/llm/messages.py`)
- Uso de **Pydantic** para definir la estructura unificada de los mensajes:
  - `Role`: Enum con los roles (`system`, `user`, `assistant`, `tool`).
  - `ToolCall`: Representa la intención del modelo de invocar una herramienta (ID, nombre, argumentos).
  - `Message`: Contiene el `role`, el contenido en texto (`content`), identificadores de llamadas a herramientas (`tool_calls` para el assistant) y resoluciones (`tool_call_id` para el rol tool).

### 2.2 Abstracción del Cliente (`src/autonomous_trading_analyst/llm/client.py`)
- Definir un `Protocol` o `ABC` llamado `LLMClient`.
- Método principal: 
  `async def generate(messages: list[Message], tools: list[dict] | None = None) -> tuple[Message, dict]`
  - Devuelve el siguiente mensaje del modelo y un diccionario (o modelo) con el uso de tokens (`prompt_tokens`, `completion_tokens`).

### 2.3 Cliente Falso / Mock (`src/autonomous_trading_analyst/llm/fake.py`)
- Clase `FakeLLMClient` que implementa `LLMClient`.
- Inicialización: Recibe una lista (o cola) pre-programada de respuestas (`list[Message]`).
- Comportamiento: 
  - En cada llamada a `generate()`, extrae (pop) el siguiente mensaje de la lista y lo devuelve.
  - Genera métricas de tokens simuladas (opcional pero útil).
  - Lanza un error explícito (ej. `RuntimeError("No more mock responses")`) si se le piden más respuestas de las configuradas.
  - Puede incluir un registro interno de los mensajes recibidos (`self.received_messages`) para hacer aserciones (asserts) en los tests posteriores.

## 3. Pruebas Unitarias (`tests/unit/test_llm_fake.py`)
- Instanciar `FakeLLMClient` con una secuencia de respuestas esperadas.
- Llamar iterativamente al método y verificar que las respuestas se retornan en orden.
- Verificar el error por agotamiento de respuestas (cuando el agente entra en loop infinito accidental).
- Validar que el cliente falso registra correctamente las entradas recibidas (historial de mensajes).

## 4. Pasos de Implementación
1. Crear el paquete `src/autonomous_trading_analyst/llm/`.
2. Implementar los modelos en `messages.py`.
3. Implementar el contrato en `client.py`.
4. Implementar la clase de simulación en `fake.py`.
5. Escribir y pasar los tests unitarios.
