import { useEffect, useMemo, useRef, useState, type FormEvent } from 'react'
import { ChevronDown, ImagePlus, Pencil, Plus, Sparkles, Trash2 } from 'lucide-react'
import { api } from './api'
import StaffModal from './StaffModal'
import ImageLightbox, { type LightboxImage } from './ImageLightbox'
import './menu-studio.css'

export type CatalogueRow = {
  category_id: string; category_name: string; item_id: string | null; item_name: string | null
  description: string | null; dietary_type: string | null; variant_id: string | null; variant_name: string | null
  offering_id: string | null; price_paise: number | null; version: number | null
  available: boolean | null; offering_active: boolean | null; estimate_max_minutes: number | null
  primary_image_url: string | null
}
type Outlet = { id: string; brand_id: string; can_edit_brand: boolean }
type Photo = { id: string; url: string; alt_text: string }
type Notify = (message: string, kind?: 'success' | 'error') => void
const MAX_PHOTOS = 10
const MAX_PHOTO_BYTES = 12 * 1024 * 1024

function photoError(files: File[], existing = 0) {
  if (files.length + existing > MAX_PHOTOS) return 'A dish can have up to 10 photos.'
  if (files.some(file => file.size > MAX_PHOTO_BYTES)) return 'Each photo must be 12 MB or less.'
  if (files.some(file => !['image/jpeg', 'image/png', 'image/webp', 'image/heic', 'image/heif'].includes(file.type) && !/\.(heic|heif)$/i.test(file.name))) return 'Choose JPEG, PNG, WebP or HEIC photos.'
  return ''
}

function CategoryPicker({ categories, value, onChange }: { categories: [string, string][]; value: string; onChange: (id: string) => void }) {
  const [open, setOpen] = useState(false)
  const root = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const close = (event: MouseEvent) => { if (!root.current?.contains(event.target as Node)) setOpen(false) }
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [])
  return <div className="menu-picker" ref={root}>
    <button type="button" className={`menu-picker-button ${open ? 'open' : ''}`} aria-expanded={open} aria-haspopup="listbox" onClick={() => setOpen(!open)}>{categories.find(([id]) => id === value)?.[1] || 'Choose a category'}<ChevronDown size={17} /></button>
    {open && <div className="menu-picker-options" role="listbox" aria-label="Categories">{categories.map(([id, name]) => <button type="button" role="option" aria-selected={id === value} key={id} onClick={() => { onChange(id); setOpen(false) }}>{name}</button>)}</div>}
  </div>
}

function SelectedPhotoPreviews({ files, onRemove, onOpen }: { files: File[]; onRemove: (index: number) => void; onOpen: (image: LightboxImage) => void }) {
  const [previews, setPreviews] = useState<{ name: string; url: string }[]>([])
  useEffect(() => {
    const next = files.map(file => ({ name: file.name, url: URL.createObjectURL(file) }))
    setPreviews(next)
    return () => next.forEach(preview => URL.revokeObjectURL(preview.url))
  }, [files])
  if (!files.length) return null
  return <div className="menu-photo-grid menu-selected-photo-grid" aria-label="Selected photos">{previews.map((preview, index) => <div className="menu-photo" key={`${preview.name}-${index}`}><button type="button" className="menu-photo-open" onClick={() => onOpen({ url: preview.url, alt: preview.name })} aria-label={`Enlarge ${preview.name}`}><img src={preview.url} alt={preview.name} /></button><button type="button" className="menu-photo-remove" onClick={() => onRemove(index)} aria-label={`Remove ${preview.name}`}><Trash2 size={15} /></button><span>{preview.name}</span></div>)}</div>
}

function PhotoManager({ itemId, onChanged, onNotify }: { itemId: string; onChanged: () => Promise<void>; onNotify: Notify }) {
  const [photos, setPhotos] = useState<Photo[]>([])
  const [files, setFiles] = useState<File[]>([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [lightbox, setLightbox] = useState<LightboxImage | null>(null)
  useEffect(() => { api.get<{ images: Photo[] }>(`/api/v1/staff/items/${itemId}/images`).then(data => setPhotos(data.images)).catch(failure => setError((failure as Error).message)) }, [itemId])
  async function upload() {
    if (!files.length) return
    const validation = photoError(files, photos.length)
    if (validation) { setError(validation); return }
    setBusy(true); setError('')
    try {
      const data = new FormData()
      files.forEach(file => data.append('images', file))
      const result = await api.upload<{ images: Photo[] }>(`/api/v1/staff/items/${itemId}/images`, data)
      setPhotos(result.images); setFiles([]); await onChanged(); onNotify('Photos uploaded to the menu.')
    } catch (failure) { setError((failure as Error).message) }
    finally { setBusy(false) }
  }
  async function remove(photo: Photo) {
    setBusy(true); setError('')
    try {
      const result = await api.delete<{ images: Photo[] }>(`/api/v1/staff/items/${itemId}/images/${photo.id}`)
      setPhotos(result.images); await onChanged(); onNotify('Photo removed from the menu.')
    } catch (failure) { setError((failure as Error).message) }
    finally { setBusy(false) }
  }
  return <div className="menu-photo-manager"><h3>Dish photos</h3><p>Upload up to 10 photos. The first photo appears on the menu card.</p><div className="menu-photo-grid">{photos.map(photo => <div className="menu-photo" key={photo.id}><button type="button" className="menu-photo-open" onClick={() => setLightbox({ url: photo.url, alt: photo.alt_text })} aria-label={`Enlarge photo of ${photo.alt_text}`}><img src={photo.url} alt={photo.alt_text} /></button><button type="button" className="menu-photo-remove" onClick={() => void remove(photo)} disabled={busy} aria-label={`Remove photo of ${photo.alt_text}`}><Trash2 size={15} /></button></div>)}{!photos.length && <span className="menu-no-photos">No photos yet</span>}</div><div className="menu-upload-row"><label className="menu-upload-pick"><ImagePlus size={17} /> Choose photos<input type="file" accept="image/jpeg,image/png,image/webp,image/heic,image/heif,.heic,.heif" multiple onChange={event => { const chosen = Array.from(event.target.files || []); const validation = photoError(chosen, photos.length); setError(validation); setFiles(validation ? [] : chosen); event.target.value = '' }} /></label><span>{files.length ? `${files.length} selected` : 'JPEG, PNG, WebP or HEIC · 12 MB each'}</span><button type="button" className="staff-primary" disabled={busy || !files.length} onClick={() => void upload()}>{busy ? 'Uploading…' : 'Upload photos'}</button></div><SelectedPhotoPreviews files={files} onRemove={index => setFiles(current => current.filter((_, fileIndex) => fileIndex !== index))} onOpen={setLightbox} />{error && <p className="menu-form-error" role="alert">{error}</p>}<ImageLightbox image={lightbox} onClose={() => setLightbox(null)} /></div>
}

export default function MenuStudio({ outlet, catalogue, onChanged, onNotify }: { outlet: Outlet; catalogue: CatalogueRow[]; onChanged: () => Promise<void>; onNotify: Notify }) {
  const [modal, setModal] = useState<'category' | 'dish' | null>(null)
  const [newCategory, setNewCategory] = useState('')
  const [editingItemId, setEditingItemId] = useState<string | null>(null)
  const [itemCategory, setItemCategory] = useState('')
  const [itemName, setItemName] = useState('')
  const [itemDescription, setItemDescription] = useState('')
  const [itemDiet, setItemDiet] = useState('VEGETARIAN')
  const [itemPrice, setItemPrice] = useState('')
  const [itemEstimate, setItemEstimate] = useState('25')
  const [itemAvailable, setItemAvailable] = useState(true)
  const [itemOnMenu, setItemOnMenu] = useState(true)
  const [itemPhotos, setItemPhotos] = useState<File[]>([])
  const [busy, setBusy] = useState(false)
  const [aiBusy, setAiBusy] = useState(false)
  const [error, setError] = useState('')
  const [showRequired, setShowRequired] = useState(false)
  const [lightbox, setLightbox] = useState<LightboxImage | null>(null)
  const categories = useMemo(() => [...new Map(catalogue.map(row => [row.category_id, row.category_name])).entries()], [catalogue])
  const items = useMemo(() => [...new Map(catalogue.filter(row => row.item_id).map(row => [row.item_id!, row])).values()], [catalogue])
  const editedRows = editingItemId ? catalogue.filter(row => row.item_id === editingItemId) : []
  const primaryOffering = editedRows.find(row => row.offering_id) || editedRows.find(row => row.variant_id)

  function openNewDish() {
    setEditingItemId(null); setItemCategory(categories[0]?.[0] || ''); setItemName(''); setItemDescription(''); setItemDiet('VEGETARIAN'); setItemPrice(''); setItemEstimate('25'); setItemAvailable(true); setItemOnMenu(true); setItemPhotos([]); setError(''); setShowRequired(false); setModal('dish')
  }
  function openEdit(row: CatalogueRow) {
    const offering = catalogue.find(entry => entry.item_id === row.item_id && entry.offering_id)
    setEditingItemId(row.item_id); setItemCategory(row.category_id); setItemName(row.item_name || ''); setItemDescription(row.description || ''); setItemDiet(row.dietary_type || 'UNSPECIFIED'); setItemPrice(offering?.price_paise != null ? (offering.price_paise / 100).toFixed(2) : ''); setItemEstimate(String(offering?.estimate_max_minutes ?? 25)); setItemAvailable(!!offering?.available); setItemOnMenu(!!offering?.offering_active); setItemPhotos([]); setError(''); setShowRequired(false); setModal('dish')
  }
  async function createCategory(event: FormEvent) {
    event.preventDefault(); setShowRequired(true); setError('')
    if (!newCategory.trim()) return
    setBusy(true)
    try {
      await api.post(`/api/v1/staff/brands/${outlet.brand_id}/categories`, { name: newCategory.trim() })
      await onChanged(); setNewCategory(''); setModal(null); onNotify('Category added.')
    } catch (failure) { setError((failure as Error).message) }
    finally { setBusy(false) }
  }
  async function deleteCategory(id: string, name: string) {
    if (!window.confirm(`Delete ${name}? Move or remove its dishes first.`)) return
    try { await api.delete(`/api/v1/staff/categories/${id}`); await onChanged(); onNotify('Category deleted.') }
    catch (failure) { onNotify((failure as Error).message, 'error') }
  }
  async function deleteItem(id: string, name: string) {
    if (!window.confirm(`Remove ${name} from the menu? Existing order history is kept.`)) return
    try { await api.delete(`/api/v1/staff/items/${id}`); await onChanged(); onNotify('Dish removed from the menu.') }
    catch (failure) { onNotify((failure as Error).message, 'error') }
  }
  async function polish() {
    if (!itemName.trim()) { setError('Enter a dish title first.'); return }
    setAiBusy(true); setError('')
    try {
      const result = await api.post<{ description: string }>(`/api/v1/staff/outlets/${outlet.id}/description-draft`, { title: itemName.trim(), draft: itemDescription.trim() })
      setItemDescription(result.description); onNotify('Description suggestion ready. Review it before saving.')
    } catch (failure) { setError((failure as Error).message) }
    finally { setAiBusy(false) }
  }
  async function saveItem(event: FormEvent) {
    event.preventDefault(); setShowRequired(true); setError('')
    if (!itemCategory || !itemName.trim()) return
    const paise = Math.round(Number(itemPrice) * 100)
    if (!itemPrice.trim() || !Number.isFinite(paise) || paise < 0) return
    const estimate = Number(itemEstimate)
    if (!itemEstimate.trim() || !Number.isInteger(estimate) || estimate < 0) return
    const validation = photoError(itemPhotos)
    if (validation) { setError(validation); return }
    setBusy(true)
    try {
      let id = editingItemId
      if (id) {
        await api.patch(`/api/v1/staff/items/${id}`, { category_id: itemCategory, name: itemName.trim(), description: itemDescription.trim(), dietary_type: itemDiet })
        if (primaryOffering?.offering_id) {
          await api.patch(`/api/v1/staff/outlets/${outlet.id}/offerings/${primaryOffering.offering_id}`, { expected_version: primaryOffering.version, price_paise: paise, estimate_max_minutes: estimate, available: itemAvailable, active: itemOnMenu })
        } else if (primaryOffering?.variant_id) {
          await api.post(`/api/v1/staff/outlets/${outlet.id}/offerings`, { variant_id: primaryOffering.variant_id, price_paise: paise, estimate_max_minutes: estimate, available: itemAvailable })
        }
      } else {
        const created = await api.post<{ item: { id: string } }>(`/api/v1/staff/outlets/${outlet.id}/quick-items`, { category_id: itemCategory, name: itemName.trim(), description: itemDescription.trim(), dietary_type: itemDiet, price_paise: paise, estimate_max_minutes: estimate })
        id = created.item.id; setEditingItemId(id)
      }
      if (itemPhotos.length) {
        const data = new FormData(); itemPhotos.forEach(file => data.append('images', file))
        try { await api.upload(`/api/v1/staff/items/${id}/images`, data); setItemPhotos([]) }
        catch (failure) { await onChanged(); setError(`Dish saved, but photo upload failed: ${(failure as Error).message}. You can retry here.`); return }
      }
      await onChanged(); setModal(null); onNotify(editingItemId ? 'Dish updated.' : 'Dish added to the menu.')
    } catch (failure) { setError((failure as Error).message) }
    finally { setBusy(false) }
  }

  return <div className="menu-studio">
    <div className="staff-section-head"><div><span className="staff-kicker">MENU STUDIO</span><h2>Your menu</h2><p>Create categories and dishes here. Available dishes appear on the guest menu after refresh.</p></div><a href={`/menu?outlet=${outlet.id}`} target="_blank" rel="noreferrer">View guest menu ↗</a></div>
    <section className="staff-panel menu-categories-panel"><div className="staff-panel-head"><div><span className="staff-kicker">ORGANIZE</span><h2>Categories</h2></div><div className="staff-head-actions"><span className="staff-muted">{categories.length} total</span>{outlet.can_edit_brand && <button className="staff-primary" onClick={() => { setError(''); setShowRequired(false); setModal('category') }}><Plus size={16} /> Add category</button>}</div></div><div className="menu-category-list">{categories.map(([id, name]) => <div className="menu-category-card" key={id}><span className="menu-category-mark">✦</span><div><strong>{name}</strong><small>{new Set(catalogue.filter(row => row.category_id === id && row.item_id).map(row => row.item_id)).size} dishes</small></div><button className="menu-icon-button" onClick={() => void deleteCategory(id, name)} aria-label={`Delete ${name}`}><Trash2 size={15} /></button></div>)}{!categories.length && <div className="staff-empty compact">No categories yet. Add one to start your menu.</div>}</div></section>
    <section className="staff-panel menu-items-panel"><div className="staff-panel-head"><div><span className="staff-kicker">CURRENT CATALOGUE</span><h2>Dishes & availability</h2></div><div className="staff-head-actions"><span className="staff-muted">{items.length} dishes</span><button className="staff-primary" onClick={openNewDish} disabled={!categories.length}><Plus size={16} /> Add dish</button></div></div>{items.length ? <div className="menu-item-list">{items.map(item => { const offer = catalogue.find(row => row.item_id === item.item_id && row.offering_id); const visible = !!offer?.offering_active && !!offer?.available; return <article className="menu-item-card" key={item.item_id}>{item.primary_image_url && <button type="button" className="menu-item-photo-button" onClick={() => setLightbox({ url: item.primary_image_url!, alt: item.item_name || "Dish photo" })} aria-label={`Enlarge photo of ${item.item_name}`}><img className="menu-item-photo" src={item.primary_image_url} alt={item.item_name || "Dish photo"} loading="lazy" /></button>}<div className="menu-item-head"><div><span>{item.category_name} · {item.dietary_type?.replaceAll('_', ' ').toLowerCase()}</span><strong className={`menu-visibility ${visible ? 'visible' : 'hidden'}`}>{visible ? 'Visible on guest menu' : 'Hidden from guest menu'}</strong><h3>{item.item_name}</h3><p>{item.description || 'No description yet.'}</p><strong className="menu-item-price">{offer?.price_paise != null ? `₹${(offer.price_paise / 100).toFixed(2)}` : 'No outlet price'}</strong></div><div className="menu-card-actions"><button onClick={() => openEdit(item)}><Pencil size={16} /> Edit</button><button className="danger" onClick={() => void deleteItem(item.item_id!, item.item_name || 'this dish')} aria-label={`Delete ${item.item_name}`}><Trash2 size={16} /></button></div></div></article> })}</div> : <div className="staff-empty compact">No dishes yet. Add your first dish when the categories are ready.</div>}</section>
    {modal === 'category' && <StaffModal title="Add category" onClose={() => setModal(null)}><form className="menu-dialog-form" onSubmit={createCategory} noValidate><label><span>Category name <span className="staff-required" aria-hidden="true">*</span></span><input value={newCategory} onChange={event => setNewCategory(event.target.value)} placeholder="e.g. Starters" maxLength={120} autoFocus required aria-invalid={showRequired && !newCategory.trim()} />{showRequired && !newCategory.trim() && <small className="staff-field-error">Enter a category name.</small>}</label>{error && <p className="menu-form-error" role="alert">{error}</p>}<div className="staff-modal-actions"><button type="button" className="staff-secondary" onClick={() => setModal(null)}>Cancel</button><button className="staff-primary" disabled={busy}>{busy ? 'Saving…' : 'Save category'}</button></div></form></StaffModal>}
    {modal === 'dish' && <StaffModal title={editingItemId ? 'Edit dish' : 'Add a dish'} onClose={() => setModal(null)} wide><form className="menu-dialog-form" onSubmit={saveItem} noValidate><div className="menu-dialog-grid"><label><span>Category <span className="staff-required" aria-hidden="true">*</span></span><CategoryPicker categories={categories} value={itemCategory} onChange={setItemCategory} />{showRequired && !itemCategory && <small className="staff-field-error">Choose a category.</small>}</label><label><span>Dish title <span className="staff-required" aria-hidden="true">*</span></span><input value={itemName} onChange={event => setItemName(event.target.value)} placeholder="e.g. Garden bowl" maxLength={160} required aria-invalid={showRequired && !itemName.trim()} />{showRequired && !itemName.trim() && <small className="staff-field-error">Enter a dish title.</small>}</label></div><label><span>Description <span className="staff-optional">(optional)</span></span><textarea value={itemDescription} onChange={event => setItemDescription(event.target.value)} placeholder="Ingredients, flavour and what makes it special" rows={4} maxLength={800} /></label><div className="menu-ai-row"><button className="menu-ai-button" type="button" disabled={aiBusy || !itemName.trim()} onClick={() => void polish()}><Sparkles size={17} /> {aiBusy ? 'Polishing…' : 'Polish with AI'}</button></div><div className="menu-dialog-grid three"><label><span>Dietary type <span className="staff-required" aria-hidden="true">*</span></span><select value={itemDiet} onChange={event => setItemDiet(event.target.value)}><option value="VEGETARIAN">Vegetarian</option><option value="VEGAN">Vegan</option><option value="NON_VEGETARIAN">Non-veg</option><option value="UNSPECIFIED">Other / unspecified</option></select></label><label><span>Price (₹) <span className="staff-required" aria-hidden="true">*</span></span><input type="number" min="0" step="0.01" value={itemPrice} onChange={event => setItemPrice(event.target.value)} placeholder="299" required aria-invalid={showRequired && (!itemPrice.trim() || !Number.isFinite(Number(itemPrice)) || Number(itemPrice) < 0)} />{showRequired && (!itemPrice.trim() || !Number.isFinite(Number(itemPrice)) || Number(itemPrice) < 0) && <small className="staff-field-error">Enter a valid price.</small>}</label><label><span>Estimate (minutes) <span className="staff-required" aria-hidden="true">*</span></span><input type="number" min="0" value={itemEstimate} onChange={event => setItemEstimate(event.target.value)} required aria-invalid={showRequired && (!itemEstimate.trim() || !Number.isInteger(Number(itemEstimate)) || Number(itemEstimate) < 0)} />{showRequired && (!itemEstimate.trim() || !Number.isInteger(Number(itemEstimate)) || Number(itemEstimate) < 0) && <small className="staff-field-error">Enter a valid estimate.</small>}</label></div>{editingItemId && <div className="menu-form-flags"><label><input type="checkbox" checked={itemOnMenu} onChange={event => setItemOnMenu(event.target.checked)} /> On menu</label><label><input type="checkbox" checked={itemAvailable} onChange={event => setItemAvailable(event.target.checked)} /> Available</label></div>}{!editingItemId && <div><label className="menu-upload-pick menu-create-upload"><ImagePlus size={17} /> Add photos<input type="file" accept="image/jpeg,image/png,image/webp,image/heic,image/heif,.heic,.heif" multiple onChange={event => { const chosen = Array.from(event.target.files || []); const validation = photoError(chosen); setError(validation); setItemPhotos(validation ? [] : chosen); event.target.value = '' }} /></label><small className="menu-help-text">{itemPhotos.length ? `${itemPhotos.length} selected` : 'Optional · up to 10 photos, 12 MB each'}</small><SelectedPhotoPreviews files={itemPhotos} onRemove={index => setItemPhotos(current => current.filter((_, fileIndex) => fileIndex !== index))} onOpen={setLightbox} /></div>}{editingItemId && <PhotoManager itemId={editingItemId} onChanged={onChanged} onNotify={onNotify} />}{error && <p className="menu-form-error" role="alert">{error}</p>}<div className="staff-modal-actions"><button type="button" className="staff-secondary" onClick={() => setModal(null)}>Cancel</button><button className="staff-primary" disabled={busy}>{busy ? 'Saving…' : editingItemId ? 'Save changes' : 'Save item'}</button></div></form></StaffModal>}
    <ImageLightbox image={lightbox} onClose={() => setLightbox(null)} />
  </div>
}
