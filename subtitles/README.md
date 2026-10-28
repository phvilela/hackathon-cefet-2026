# Legendas do pitch

Gera legendas `.srt` em português para o vídeo do pitch usando [faster-whisper](https://github.com/SYSTRAN/faster-whisper) ( Whisper da OpenAI otimizado para CPU).

## Setup

```bash
# a partir da raiz do repositório (usa o .venv existente)
.venv/bin/pip install -r subtitles/requirements.txt
```

Na primeira execução o modelo `small` (~460MB) é baixado automaticamente e fica em cache.

## Uso

```bash
# caminho do vídeo por argumento
.venv/bin/python subtitles/generate_subtitles.py caminho/do/pitch.mp4

# sem argumento → usa subtitles/pitch.mp4
.venv/bin/python subtitles/generate_subtitles.py
```

Saída: `<nome_do_video>.srt` ao lado do vídeo.

## Opções

| Opção | Padrão | Descrição |
|---|---|---|
| `input` | `subtitles/pitch.mp4` | Caminho do vídeo/áudio |
| `--model` | `small` | Modelo Whisper (`small` é o equilíbrio rápido/preciso em CPU) |
| `--language` | `pt` | Idioma da fala |
| `--output` | `<input>.srt` | Caminho do `.srt` de saída |

## Detalhes

- Áudio do vídeo é decodificado direto com PyAV (sem passos intermediários).
- `vad_filter=True` corta silêncios e reduz alucinações do modelo.
- `av<19` está fixado por incompatibilidade do faster-whisper 1.2.1 com PyAV 19
  ([issue #1589](https://github.com/SYSTRAN/faster-whisper/issues/1589)).
- Requer Python 3.12+ e o `.venv` do repositório.

## Resultado

```
1
00:00:00,000 --> 00:00:02,500
Olá, somos o time do projeto.
```
