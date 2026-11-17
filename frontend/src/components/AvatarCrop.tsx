import { Alert, Button, Group, Modal, Slider, Stack, Text } from "@mantine/core";
import { IconZoomIn, IconZoomOut } from "@tabler/icons-react";
import { type PointerEvent as ReactPointerEvent, type WheelEvent, useEffect, useRef, useState } from "react";
import { useT } from "../i18n";

const STAGE = 280; // px, the square the circle sits in
const OUT = 512; // px, size of the uploaded square
const MAX_ZOOM = 5;

type View = { x: number; y: number; zoom: number };

/**
 * WhatsApp-style picture crop: the picture behind a round window, drag to
 * move, pinch / wheel / slider to zoom. The square around the circle is
 * exported (the portal shows every avatar round).
 */
export function AvatarCropDialog({ file, onCancel, onDone }: { file: File | null; onCancel: () => void; onDone: (cropped: File) => void }) {
  const t = useT();
  const [src, setSrc] = useState<string | null>(null);
  const [size, setSize] = useState<{ w: number; h: number } | null>(null);
  const [failed, setFailed] = useState(false);
  const [view, setView] = useState<View>({ x: 0, y: 0, zoom: 1 });
  const imgRef = useRef<HTMLImageElement>(null);
  const pointers = useRef(new Map<number, { x: number; y: number }>());
  const pinch = useRef<{ dist: number; zoom: number } | null>(null);

  useEffect(() => {
    setSize(null);
    setFailed(false);
    if (!file) return setSrc(null);
    const url = URL.createObjectURL(file);
    setSrc(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  const base = size ? STAGE / Math.min(size.w, size.h) : 1; // "cover" scale
  // Keep the circle covered: the picture never leaves the square.
  const clamp = (v: View): View => {
    if (!size) return v;
    const zoom = Math.min(MAX_ZOOM, Math.max(1, v.zoom));
    const s = base * zoom;
    const minX = STAGE - size.w * s;
    const minY = STAGE - size.h * s;
    return { zoom, x: Math.min(0, Math.max(minX, v.x)), y: Math.min(0, Math.max(minY, v.y)) };
  };
  // Zoom around a point of the stage (default: its centre).
  const zoomTo = (zoom: number, cx = STAGE / 2, cy = STAGE / 2) =>
    setView((v) => {
      const next = Math.min(MAX_ZOOM, Math.max(1, zoom));
      const f = next / v.zoom;
      return clamp({ zoom: next, x: cx - (cx - v.x) * f, y: cy - (cy - v.y) * f });
    });

  const onLoad = () => {
    const img = imgRef.current;
    if (!img) return;
    const w = img.naturalWidth;
    const h = img.naturalHeight;
    const s = STAGE / Math.min(w, h);
    setSize({ w, h });
    setView({ zoom: 1, x: (STAGE - w * s) / 2, y: (STAGE - h * s) / 2 });
  };

  const local = (e: ReactPointerEvent) => {
    const r = (e.currentTarget as HTMLElement).getBoundingClientRect();
    return { x: e.clientX - r.left, y: e.clientY - r.top };
  };
  const down = (e: ReactPointerEvent) => {
    (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
    pointers.current.set(e.pointerId, local(e));
    if (pointers.current.size === 2) {
      const [a, b] = [...pointers.current.values()];
      pinch.current = { dist: Math.hypot(a.x - b.x, a.y - b.y), zoom: view.zoom };
    }
  };
  const move = (e: ReactPointerEvent) => {
    const prev = pointers.current.get(e.pointerId);
    if (!prev) return;
    const now = local(e);
    pointers.current.set(e.pointerId, now);
    if (pointers.current.size >= 2 && pinch.current) {
      const [a, b] = [...pointers.current.values()];
      zoomTo(pinch.current.zoom * (Math.hypot(a.x - b.x, a.y - b.y) / pinch.current.dist), (a.x + b.x) / 2, (a.y + b.y) / 2);
    } else {
      setView((v) => clamp({ ...v, x: v.x + now.x - prev.x, y: v.y + now.y - prev.y }));
    }
  };
  const up = (e: ReactPointerEvent) => {
    pointers.current.delete(e.pointerId);
    if (pointers.current.size < 2) pinch.current = null;
  };
  const wheel = (e: WheelEvent) => {
    const r = e.currentTarget.getBoundingClientRect();
    zoomTo(view.zoom * (1 - e.deltaY * 0.0015), e.clientX - r.left, e.clientY - r.top);
  };

  const save = () => {
    const img = imgRef.current;
    if (!img || !size) return;
    const s = base * view.zoom;
    const canvas = document.createElement("canvas");
    canvas.width = OUT;
    canvas.height = OUT;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.fillStyle = "#fff";
    ctx.fillRect(0, 0, OUT, OUT);
    ctx.imageSmoothingQuality = "high";
    ctx.drawImage(img, -view.x / s, -view.y / s, STAGE / s, STAGE / s, 0, 0, OUT, OUT);
    canvas.toBlob((blob) => blob && onDone(new File([blob], "avatar.jpg", { type: "image/jpeg" })), "image/jpeg", 0.9);
  };

  const s = base * view.zoom;
  return (
    <Modal opened={file !== null} onClose={onCancel} title={<Text fw={800}>{t("Choose the picture section")}</Text>} size="auto" centered>
      <Stack gap="md" align="center" w={STAGE}>
        {failed ? (
          <Alert color="red">{t("The browser cannot show this picture. Please choose a JPG or PNG.")}</Alert>
        ) : (
          <div
            className="avatar-crop-stage"
            onPointerDown={down}
            onPointerMove={move}
            onPointerUp={up}
            onPointerCancel={up}
            onWheel={wheel}
            style={{ position: "relative", width: STAGE, height: STAGE, overflow: "hidden", touchAction: "none", cursor: "grab", borderRadius: 8, background: "#000", userSelect: "none" }}
          >
            {src && (
              <img
                ref={imgRef}
                src={src}
                alt=""
                draggable={false}
                onLoad={onLoad}
                onError={() => setFailed(true)}
                style={{ position: "absolute", left: view.x, top: view.y, width: size ? size.w * s : "auto", height: size ? size.h * s : "auto", maxWidth: "none", visibility: size ? "visible" : "hidden" }}
              />
            )}
            {/* the round window: everything outside is dimmed */}
            <div style={{ position: "absolute", inset: 0, borderRadius: "50%", boxShadow: "0 0 0 9999px rgba(0,0,0,.6)", border: "2px solid rgba(255,255,255,.9)", pointerEvents: "none" }} />
          </div>
        )}
        {!failed && (
          <Group gap="xs" w="100%" wrap="nowrap">
            <IconZoomOut size={18} style={{ flexShrink: 0 }} />
            <Slider style={{ flex: 1 }} min={1} max={MAX_ZOOM} step={0.01} value={view.zoom} onChange={(z) => zoomTo(z)} label={null} aria-label={t("Zoom")} />
            <IconZoomIn size={18} style={{ flexShrink: 0 }} />
          </Group>
        )}
        <Text size="xs" c="dimmed" ta="center">{t("Drag to move, pinch or use the slider to zoom.")}</Text>
        <Group justify="flex-end" w="100%">
          <Button color="gray" onClick={onCancel}>{t("Cancel")}</Button>
          <Button onClick={save} disabled={!size || failed}>{t("Use picture")}</Button>
        </Group>
      </Stack>
    </Modal>
  );
}
