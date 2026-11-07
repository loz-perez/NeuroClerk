# Plugins de DSH usados en NeuroClerk

*Actualizado el 7 de noviembre de 2026.*

Los plugins de DeepSeek Harness viven en el perfil `~/.dsh/profiles/desktop`, **no en este repositorio**. Este documento fija cuáles se usan, para qué sirven y cómo revertirlos. No son dependencias de `rag.py` ni deben agregarse a `requirements.txt`.

## Instalados

| Plugin | Versión | Qué aporta |
| --- | --- | --- |
| `@deepseek-ai/dsh-experimental-plugin-market-bundle` | 0.2.2-rc.1 | Pestaña de plugins y market en Ajustes |
| `@deepseek-ai/dsh-experimental-session-search` | 0.2.2-rc.1 | `session_search` y lectura de sesiones anteriores |
| `dsh-files` | 0.7.0 (`github:taxueseek/dsh-files#v0.7.0`) | `read_document`, adjuntos y exportación |
| `dsh-plugin` | 2.3.5 | Hub comunitario dentro de la app |

## Cómo se usan en el proyecto

- **`read_document`**: leer páginas concretas de los PDFs sin escribir scripts de `pypdf`. Sirve para verificar el dato exacto de un caso, por ejemplo CIE-11 páginas 503-505, mhGAP página 37 o PHQ-9 página 2. No indexa, no reemplaza a `probar_rag.py --ranking` y no forma parte del RAG que responde.
- **`attachment_list` / `export_attachment`**: incorporar un archivo subido al workspace y copiarlo a una ruta de trabajo.
- **`session_search`**: recuperar decisiones anteriores del proyecto (por qué quedó un parámetro, qué se probó en un caso). No es una fuente clínica.
- **Plugin Hub**: revisar, instalar o desinstalar plugins. No interviene en las respuestas del asistente.

## Verificación

El 07/11/2026 se probó `read_document` sobre `datos/CIE-11.pdf`, página 504: devolvió la tabla de equivalencias CIE-10/CIE-11 y confirmó que el plugin lee rutas del workspace de WSL (`\\wsl.localhost\Ubuntu\...`) sin scripts intermedios.

## Seguridad

- `dsh-files` v0.7.0 es MIT, no hace llamadas externas, no trae binarios nativos y lee a través del mismo sandbox que el `read` nativo. El límite quedó en 48 MB, así entra el DSM-5-TR (30,4 MB).
- Los plugins corren con el mismo acceso que la sesión. Este perfil no pide aprobaciones, así que solo se instalan versiones fijadas y auditadas.
- No se instalan plugins de RAG, memoria, OCR ni ofimática: duplican el diseño del proyecto o aumentan el riesgo de filtrar documentos clínicos.

## Configuración

En `~/.dsh/profiles/desktop/package.json` están las dependencias y los bundles. En `~/.dsh/profiles/desktop/cordis.patch.yml` está el ajuste de `dsh-files`:

```yaml
- id: files-toolkit
  name: "dsh-files"
  config:
    maxFileBytes: 50331648   # 48 MB
    readLimit: 2000
    sheetRowLimit: 200
    maxSheets: 5
    maxOutputChars: 24000
    readTimeoutMs: 120000
    attachmentsEnabled: true
    maxDownloadBytes: 209715200
```

La app quedó configurada en inglés (`locale: en`) para que el hub use ese idioma.

## Revertir

1. Quitar de `dependencies` y de `dsh.profile.bundles` los paquetes que se quieran desinstalar.
2. Borrar `~/.dsh/profiles/desktop/node_modules`.
3. Quitar la entrada `files-toolkit` de `cordis.patch.yml` si se va `dsh-files`.
4. Reiniciar DeepSeek Harness.

## Qué no se instala

- RAG o bases de conocimiento externas: chocan con el RAG escrito a mano y pueden sacar PDFs de la máquina.
- Memoria o contexto persistente: duplica `HOJA_DE_RUTA.md` y `CLAUDE.md`, y puede citar hechos viejos.
- OCR: queda para cuando se agregue OCR al proyecto.
- Excel/ofimática: ya está el skill `office-xlsx`.
- Proveedores “gratis sin clave” o plugins sin auditoría: riesgo de supply chain y de envío de datos.
