"""Validação e preparo das fotos enviadas ao Personal IA (sem interface).

Toda foto é aberta pelo Pillow (dependência do próprio Streamlit) e regravada como JPEG: o formato é conferido pelo
conteúdo, não pelo nome do arquivo; a orientação da câmera é aplicada; o tamanho cai para no máximo 1568 px no lado
maior (o que o modelo aproveita); e os metadados (EXIF, GPS, modelo do celular) não são copiados.
"""
from __future__ import annotations

import io

from PIL import Image, ImageOps, UnidentifiedImageError

FORMATOS = {"JPEG": "JPEG", "PNG": "PNG", "WEBP": "WebP"}
LADO_MAXIMO = 1568
PIXELS_MAXIMOS = 40_000_000  # acima disso a foto é recusada antes de ser decodificada (proteção contra "bombas")
QUALIDADE = 85


class ImagemInvalida(ValueError):
    """Arquivo que não é foto aceita, ou grande demais (mensagem pronta para mostrar)."""


def preparar(dados: bytes, max_bytes: int) -> dict:
    """Confere e regrava a foto. Devolve {"bytes", "mime", "largura", "altura"} ou levanta ImagemInvalida."""
    if not dados:
        raise ImagemInvalida("O arquivo está vazio.")
    if len(dados) > max_bytes:
        raise ImagemInvalida(f"A foto tem {len(dados) / 1_048_576:.1f} MB; o limite é {max_bytes / 1_048_576:.0f} MB.")
    try:
        with Image.open(io.BytesIO(dados)) as img:
            formato = img.format
            largura, altura = img.size
            if formato not in FORMATOS:
                raise ImagemInvalida("Formato não aceito. Envie uma foto JPEG, PNG ou WebP.")
            if largura * altura > PIXELS_MAXIMOS:
                raise ImagemInvalida("A foto tem resolução alta demais. Envie uma versão menor.")
            img.verify()  # detecta arquivo truncado ou corrompido
        with Image.open(io.BytesIO(dados)) as img:
            img = ImageOps.exif_transpose(img)  # aplica a orientação da câmera antes de descartar o EXIF
            if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
                fundo = Image.new("RGB", img.size, (255, 255, 255))
                fundo.paste(img.convert("RGBA"), mask=img.convert("RGBA").getchannel("A"))
                img = fundo
            else:
                img = img.convert("RGB")
            img.thumbnail((LADO_MAXIMO, LADO_MAXIMO))
            saida = io.BytesIO()
            img.save(saida, format="JPEG", quality=QUALIDADE, optimize=True)  # sem exif=: nenhum metadado
            return {"bytes": saida.getvalue(), "mime": "image/jpeg", "largura": img.width, "altura": img.height}
    except ImagemInvalida:
        raise
    except (UnidentifiedImageError, Image.DecompressionBombError) as e:
        raise ImagemInvalida("O arquivo não é uma foto válida. Envie JPEG, PNG ou WebP.") from e
    except (OSError, ValueError, SyntaxError) as e:
        raise ImagemInvalida("A foto está corrompida ou incompleta. Tente enviar de novo.") from e
