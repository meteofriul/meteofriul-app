#!/usr/bin/env python3
"""Prepare a transparent, cropped, slowed Home eagle animation."""

from __future__ import annotations

import argparse
from pathlib import Path

import imageio_ffmpeg
import numpy as np
from PIL import Image, ImageFilter


DEFAULT_CROP = (170, 70, 790, 780)
SAFE_CONTENT_BOUNDS = (32, 32, 588, 690)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--playback-rate", type=float, default=0.55)
    parser.add_argument("--width", type=int, default=280)
    parser.add_argument("--background-threshold", type=int, default=235)
    return parser.parse_args()


def remove_connected_background(image: Image.Image, threshold: int) -> Image.Image:
    rgb = image.convert("RGB")
    pixels = np.asarray(rgb)
    minimum = pixels.min(axis=2)
    spread = np.ptp(pixels, axis=2)
    alpha = Image.fromarray(
        np.where((minimum >= threshold) & (spread <= 24), 0, 255).astype(np.uint8),
        mode="L",
    )
    alpha = alpha.filter(ImageFilter.MedianFilter(3))
    alpha = alpha.filter(ImageFilter.MinFilter(3))

    rgba = np.asarray(rgb.convert("RGBA")).copy()
    alpha_pixels = np.asarray(alpha)
    rgba[:, :, 3] = alpha_pixels
    rgba[alpha_pixels == 0, :3] = 0
    return Image.fromarray(rgba, mode="RGBA")


def union_bbox(
    current: tuple[int, int, int, int] | None,
    incoming: tuple[int, int, int, int] | None,
) -> tuple[int, int, int, int] | None:
    if incoming is None:
        return current
    if current is None:
        return incoming
    return (
        min(current[0], incoming[0]),
        min(current[1], incoming[1]),
        max(current[2], incoming[2]),
        max(current[3], incoming[3]),
    )


def expand_bbox(
    bbox: tuple[int, int, int, int],
    size: tuple[int, int],
    margin: int = 12,
) -> tuple[int, int, int, int]:
    return (
        max(0, bbox[0] - margin),
        max(0, bbox[1] - margin),
        min(size[0], bbox[2] + margin),
        min(size[1], bbox[3] + margin),
    )


def clamp_bbox(
    bbox: tuple[int, int, int, int],
    bounds: tuple[int, int, int, int],
) -> tuple[int, int, int, int]:
    return (
        max(bbox[0], bounds[0]),
        max(bbox[1], bounds[1]),
        min(bbox[2], bounds[2]),
        min(bbox[3], bounds[3]),
    )


def main() -> None:
    args = parse_args()
    if not 0 < args.playback_rate <= 1:
        raise ValueError("playback rate must be greater than 0 and no more than 1")

    reader = imageio_ffmpeg.read_frames(str(args.input), pix_fmt="rgb24")
    metadata = next(reader)
    source_size = tuple(metadata["size"])
    fps = float(metadata.get("fps") or 24)
    crop = DEFAULT_CROP
    crop_size = (crop[2] - crop[0], crop[3] - crop[1])

    frames: list[Image.Image] = []
    content_bbox: tuple[int, int, int, int] | None = None
    for raw_frame in reader:
        frame = Image.frombytes("RGB", source_size, raw_frame).crop(crop)
        transparent = remove_connected_background(frame, args.background_threshold)
        content_bbox = union_bbox(content_bbox, transparent.getchannel("A").getbbox())
        frames.append(transparent)

    if not frames or content_bbox is None:
        raise RuntimeError("no eagle frames were extracted")

    content_bbox = clamp_bbox(
        expand_bbox(content_bbox, crop_size),
        SAFE_CONTENT_BOUNDS,
    )
    output_frames: list[Image.Image] = []
    for frame in frames:
        frame = frame.crop(content_bbox)
        height = round(frame.height * args.width / frame.width)
        output_frames.append(
            frame.convert("RGBa")
            .resize((args.width, height), Image.Resampling.LANCZOS)
            .convert("RGBA")
        )

    frame_duration_ms = round(1000 / fps / args.playback_rate)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.output.suffix.lower() == ".png":
        output_frames[0].save(
            args.output,
            "PNG",
            append_images=output_frames[1:],
            blend=0,
            disposal=2,
            duration=frame_duration_ms,
            loop=0,
            optimize=True,
            save_all=True,
        )
    else:
        output_frames[0].save(
            args.output,
            "WEBP",
            append_images=output_frames[1:],
            duration=frame_duration_ms,
            kmax=1,
            kmin=1,
            loop=0,
            lossless=True,
            method=6,
            save_all=True,
        )

    print(
        f"frames={len(output_frames)} fps={fps:g} duration={frame_duration_ms}ms "
        f"crop={content_bbox} output={output_frames[0].size}"
    )


if __name__ == "__main__":
    main()
