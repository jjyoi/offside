import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { motion, useMotionValue } from "motion/react";

const SIZE = 56;
const GRAVITY = 1800;
const RESTITUTION = 0.72;
const FRICTION = 0.995;

export function BouncingBall({ onDismiss }: { onDismiss: () => void }) {
  const x = useMotionValue(0);
  const y = useMotionValue(0);
  const vx = useRef(320);
  const vy = useRef(-200);
  const dragging = useRef(false);
  const frame = useRef<number>(0);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    x.set(window.innerWidth * 0.7);
    y.set(window.innerHeight * 0.3);
    setReady(true);

    let last = performance.now();
    const tick = (now: number) => {
      const dt = Math.min((now - last) / 1000, 0.032);
      last = now;

      if (!dragging.current) {
        vy.current += GRAVITY * dt;
        vx.current *= FRICTION;

        let nx = x.get() + vx.current * dt;
        let ny = y.get() + vy.current * dt;

        const maxX = window.innerWidth - SIZE;
        const maxY = window.innerHeight - SIZE;

        if (nx <= 0) {
          nx = 0;
          vx.current = Math.abs(vx.current) * RESTITUTION;
        } else if (nx >= maxX) {
          nx = maxX;
          vx.current = -Math.abs(vx.current) * RESTITUTION;
        }

        if (ny >= maxY) {
          ny = maxY;
          vy.current = -Math.abs(vy.current) * RESTITUTION;
          if (Math.abs(vy.current) < 60) vy.current = 0;
        } else if (ny <= 0) {
          ny = 0;
          vy.current = Math.abs(vy.current) * RESTITUTION;
        }

        x.set(nx);
        y.set(ny);
      }

      frame.current = requestAnimationFrame(tick);
    };

    frame.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame.current);
  }, [x, y]);

  if (!ready) return null;

  return createPortal(
    <motion.button
      type="button"
      className="bouncing-ball"
      style={{ x, y, width: SIZE, height: SIZE }}
      drag
      dragMomentum={false}
      dragElastic={0}
      onDragStart={() => {
        dragging.current = true;
      }}
      onDrag={(_, info) => {
        vx.current = info.delta.x * 45;
        vy.current = info.delta.y * 45;
      }}
      onDragEnd={() => {
        dragging.current = false;
      }}
      onDoubleClick={onDismiss}
      title="Overturned! Kick the ball around — double-click to put it away"
      aria-label="Bouncing soccer ball, draggable. Double-click to dismiss."
      initial={{ scale: 0 }}
      animate={{ scale: 1, rotate: 360 }}
      transition={{ scale: { type: "spring", stiffness: 300, damping: 18 }, rotate: { duration: 1.4, repeat: Infinity, ease: "linear" } }}
    />,
    document.body,
  );
}
