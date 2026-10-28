#!/usr/bin/env python3
"""Gera legendas .srt em português para o vídeo do pitch (hackathon)."""

import argparse
import sys
from pathlib import Path


def format_timestamp(seconds: float) -> str:
    ms = int(round(seconds * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1_000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def write_srt(segments, output_path: Path) -> int:
    count = 0
    with output_path.open("w", encoding="utf-8") as f:
        for segment in segments:
            text = segment.text.strip()
            if not text:
                continue
            count += 1
            f.write(f"{count}\n")
            f.write(
                f"{format_timestamp(segment.start)} --> {format_timestamp(segment.end)}\n"
            )
            f.write(f"{text}\n\n")
    return count


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Gera legendas .srt em português a partir do vídeo do pitch."
    )
    parser.add_argument(
        "input",
        nargs="?",
        default=str(Path(__file__).parent / "pitch.mp4"),
        help="Caminho do vídeo/áudio (padrão: subtitles/pitch.mp4)",
    )
    parser.add_argument(
        "--model",
        default="small",
        help="Modelo do Whisper (padrão: small)",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Caminho do .srt de saída (padrão: <input>.srt)",
    )
    parser.add_argument(
        "--language",
        default="pt",
        help="Idioma da fala (padrão: pt)",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Arquivo não encontrado: {input_path}", file=sys.stderr)
        print(
            "Coloque o vídeo do pitch em subtitles/pitch.mp4 ou informe o caminho.",
            file=sys.stderr,
        )
        return 1

    output_path = (
        Path(args.output) if args.output else input_path.with_suffix(".srt")
    )

    from faster_whisper import WhisperModel

    print(f"Carregando modelo '{args.model}' (CPU, int8)...")
    model = WhisperModel(args.model, device="cpu", compute_type="int8")

    print(f"Transcrevendo {input_path.name} (idioma={args.language})...")
    segments, info = model.transcribe(
        str(input_path),
        language=args.language,
        vad_filter=True,
        beam_size=5,
    )

    count = write_srt(segments, output_path)
    print(f"Idioma detectado: {info.language} (prob. {info.language_probability:.2f})")
    print(f"{count} legendas gravadas em {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
