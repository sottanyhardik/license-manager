import { useEffect, useState, type CSSProperties } from "react";
import api from "../api/axios";

/**
 * <img> for files behind authentication. A plain `<img src="/media/...">` can't
 * send the Authorization header, so once media is served only via the
 * authenticated /api/media/<path> endpoint, direct src URLs stop loading. This
 * fetches the file through the axios instance (auth header) as a Blob and renders
 * it from a short-lived object URL.
 */
interface AuthedImageProps {
  /** Path relative to the axios baseURL, e.g. "/media/uploads/foo.png". */
  path: string;
  alt?: string;
  style?: CSSProperties;
  className?: string;
}

export default function AuthedImage({ path, alt, style, className }: AuthedImageProps) {
  const [src, setSrc] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let objectUrl: string | null = null;
    let cancelled = false;
    setFailed(false);
    setSrc(null);
    api
      .get(path, { responseType: "blob" })
      .then((res) => {
        if (cancelled) return;
        objectUrl = URL.createObjectURL(res.data as Blob);
        setSrc(objectUrl);
      })
      .catch(() => {
        if (!cancelled) setFailed(true);
      });
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [path]);

  if (failed) return null;
  if (!src) return <span aria-hidden="true" style={style} className={className} />;
  return <img src={src} alt={alt} style={style} className={className} />;
}
