import { useState } from "react";
import { apiUrl } from "../lib/api";
import { placeholderFor } from "../lib/format";
import { cx } from "./ui";

/**
 * Evidence photo with a guaranteed fallback.
 *
 * Citizens usually report without a photo, so every card used to grab a random
 * stock image from the internet. Now a missing photo shows a local,
 * category-specific placeholder — offline-safe and honest about being art.
 */
export default function EvidenceImage({ src, category, alt = "Incident evidence", className = "", imgClassName = "" }) {
  const [failed, setFailed] = useState(false);
  const resolved = src && !failed ? apiUrl(src) : placeholderFor(category);

  return (
    <div className={cx("relative overflow-hidden bg-slate-100", className)}>
      <img
        src={resolved}
        alt={alt}
        loading="lazy"
        onError={() => setFailed(true)}
        className={cx("h-full w-full object-cover", imgClassName)}
      />
      {(!src || failed) && (
        <span className="absolute bottom-1.5 right-1.5 rounded bg-white/85 px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wider text-slate-500">
          illustrative
        </span>
      )}
    </div>
  );
}
