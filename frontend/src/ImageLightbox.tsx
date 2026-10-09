import { useEffect } from 'react'
import { createPortal } from 'react-dom'
import { X } from 'lucide-react'

export type LightboxImage = { url: string; alt: string }

export default function ImageLightbox({ image, onClose }: { image: LightboxImage | null; onClose: () => void }) {
  useEffect(() => {
    if (!image) return
    const onKeyDown = (event: KeyboardEvent) => { if (event.key === 'Escape') onClose() }
    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [image, onClose])
  if (!image) return null
  return createPortal(<div className="menu-image-lightbox" role="dialog" aria-modal="true" aria-label={image.alt} onMouseDown={event => { if (event.target === event.currentTarget) onClose() }}>
    <button className="menu-image-lightbox-close" type="button" onClick={onClose} aria-label="Close image"><X size={22} /></button>
    <img src={image.url} alt={image.alt} />
    <span>{image.alt}</span>
  </div>, document.body)
}
