import { useEffect, useMemo, useState, type FormEvent } from 'react'
import { ChevronDown, ImagePlus, Plus, Sparkles, Trash2 } from 'lucide-react'
import { api } from './api'
import './menu-studio.css'

export type CatalogueRow = {
  category_id: string; category_name: string; item_id: string | null; item_name: string | null
  description: string | null; dietary_type: string | null; variant_id: string | null; variant_name: string | null
  offering_id: string | null; price_paise: number | null; version: number | null
  available: boolean | null; offering_active: boolean | null; estimate_max_minutes: number | null
}

type Outlet = { id: string; brand_id: string; can_edit_brand: boolean }
type Photo = { id: string; url: string; alt_text: string }
const MAX_PHOTOS = 10
const MAX_PHOTO_BYTES = 6 * 1024 * 1024

function photoError(files: File[], existing = 0) {
  if (files.length + existing > MAX_PHOTOS) return 'A dish can have up to 10 photos.'
  if (files.some(file => file.size > MAX_PHOTO_BYTES)) return 'Each photo must be 6 MB or less.'
  return ''
}

function OfferingEditor({ row, outletId, onChanged }: { row: CatalogueRow; outletId: string; onChanged: () => Promise<void> }) {
  const [price, setPrice] = useState(((row.price_paise || 0) / 100).toFixed(2))
  const [available, setAvailable] = useState(!!row.available)
  const [active, setActive] = useState(!!row.offering_active)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  useEffect(() => { setPrice(((row.price_paise || 0) / 100).toFixed(2)); setAvailable(!!row.available); setActive(!!row.offering_active) }, [row.price_paise, row.available, row.offering_active])
  async function save() {
    const paise = Math.round(Number(price) * 100)
    if (!Number.isFinite(paise) || paise < 0) { setError('Enter a valid price.'); return }
    setBusy(true); setError('')
    try {
      await api.patch(`/api/v1/staff/outlets/${outletId}/offerings/${row.offering_id}`, { expected_version: row.version, price_paise: paise, available, active })
      await onChanged()
    } catch (failure) { setError((failure as Error).message) }
    finally { setBusy(false) }
  }
  return <div className="menu-offering"><span className="menu-offering-name">{row.variant_name || 'Regular'}</span><label>Price ₹<input type="number" min="0" step="0.01" value={price} onChange={event => setPrice(event.target.value)} /></label><label className="menu-availability"><input type="checkbox" checked={active} onChange={event => setActive(event.target.checked)} /> On menu</label><label className="menu-availability"><input type="checkbox" checked={available} onChange={event => setAvailable(event.target.checked)} /> Available</label><button disabled={busy || (price === ((row.price_paise || 0) / 100).toFixed(2) && available === !!row.available && active === !!row.offering_active)} onClick={() => void save()}>Save</button>{error && <small role="alert">{error}</small>}</div>
}

function AddOffering({ row, outletId, onChanged }: { row: CatalogueRow; outletId: string; onChanged: () => Promise<void> }) {
  const [price, setPrice] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  async function save() {
    const paise = Math.round(Number(price) * 100)
    if (!price.trim() || !Number.isFinite(paise) || paise < 0) { setError('Enter a valid price.'); return }
    setBusy(true); setError('')
    try {
      await api.post(`/api/v1/staff/outlets/${outletId}/offerings`, { variant_id: row.variant_id, price_paise: paise, estimate_min_minutes: 0, estimate_max_minutes: 25, available: true })
      await onChanged()
    } catch (failure) { setError((failure as Error).message) }
    finally { setBusy(false) }
  }
  return <div className="menu-offering"><span className="menu-offering-name">{row.variant_name || 'Regular'} · not offered at this outlet</span><label>Price ₹<input type="number" min="0" step="0.01" value={price} onChange={event => setPrice(event.target.value)} placeholder="299" /></label><button disabled={busy} onClick={() => void save()}>Add to menu</button>{error && <small role="alert">{error}</small>}</div>
}

function PhotoManager({ itemId, onChanged }: { itemId: string; onChanged: () => Promise<void> }) {
  const [photos, setPhotos] = useState<Photo[]>([])
  const [files, setFiles] = useState<File[]>([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
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
      setPhotos(result.images); setFiles([]); await onChanged()
    } catch (failure) { setError((failure as Error).message) }
    finally { setBusy(false) }
  }
  async function remove(photo: Photo) {
    setBusy(true); setError('')
    try {
      const result = await api.delete<{ images: Photo[] }>(`/api/v1/staff/items/${itemId}/images/${photo.id}`)
      setPhotos(result.images); await onChanged()
    } catch (failure) { setError((failure as Error).message) }
    finally { setBusy(false) }
  }
  return <div className="menu-photo-manager"><div className="menu-photo-grid">{photos.map(photo => <div className="menu-photo" key={photo.id}><img src={photo.url} alt={photo.alt_text} /><button onClick={() => void remove(photo)} disabled={busy} aria-label={`Remove photo of ${photo.alt_text}`}><Trash2 size={15} /></button></div>)}{!photos.length && <p>No photos yet. The menu will use its image placeholder.</p>}</div><div className="menu-upload-row"><label className="menu-upload-pick"><ImagePlus size={17} /> Choose photos<input type="file" accept="image/jpeg,image/png,image/webp" multiple onChange={event => setFiles(Array.from(event.target.files || []))} /></label><span>{files.length ? `${files.length} selected` : 'JPEG, PNG or WebP · up to 6 MB each · 10 total'}</span><button className="staff-primary" disabled={busy || !files.length} onClick={() => void upload()}>{busy ? 'Working…' : 'Upload photos'}</button></div>{error && <p className="menu-form-error" role="alert">{error}</p>}</div>
}

export default function MenuStudio({ outlet, catalogue, onChanged }: { outlet: Outlet; catalogue: CatalogueRow[]; onChanged: () => Promise<void> }) {
  const [newCategory, setNewCategory] = useState('')
  const [itemCategory, setItemCategory] = useState('')
  const [itemName, setItemName] = useState('')
  const [itemDescription, setItemDescription] = useState('')
  const [itemDiet, setItemDiet] = useState('VEGETARIAN')
  const [itemPrice, setItemPrice] = useState('')
  const [itemEstimate, setItemEstimate] = useState('25')
  const [itemPhotos, setItemPhotos] = useState<File[]>([])
  const [expandedItem, setExpandedItem] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [aiBusy, setAiBusy] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const categories = useMemo(() => [...new Map(catalogue.map(row => [row.category_id, row.category_name])).entries()], [catalogue])
  const items = useMemo(() => [...new Map(catalogue.filter(row => row.item_id).map(row => [row.item_id!, row])).values()], [catalogue])

  async function createCategory(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError(''); setMessage('')
    try {
      await api.post(`/api/v1/staff/brands/${outlet.brand_id}/categories`, { name: newCategory.trim() })
      setNewCategory(''); await onChanged(); setMessage('Category added. It is ready for dishes.')
    } catch (failure) { setError((failure as Error).message) }
    finally { setBusy(false) }
  }
  async function polish() {
    if (!itemName.trim()) { setError('Enter a dish title first.'); return }
    setAiBusy(true); setError(''); setMessage('')
    try {
      const result = await api.post<{ description: string }>(`/api/v1/staff/outlets/${outlet.id}/description-draft`, { title: itemName.trim(), draft: itemDescription.trim() })
      setItemDescription(result.description); setMessage('AI suggestion added. Review it before saving.')
    } catch (failure) { setError((failure as Error).message) }
    finally { setAiBusy(false) }
  }
  async function createItem(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError(''); setMessage('')
    const validation = photoError(itemPhotos)
    if (validation) { setError(validation); setBusy(false); return }
    const paise = Math.round(Number(itemPrice) * 100)
    if (!Number.isFinite(paise) || paise < 0) { setError('Enter a valid price.'); setBusy(false); return }
    try {
      const created = await api.post<{ item: { id: string } }>(`/api/v1/staff/outlets/${outlet.id}/quick-items`, { category_id: itemCategory, name: itemName.trim(), description: itemDescription.trim(), dietary_type: itemDiet, price_paise: paise, estimate_max_minutes: Number(itemEstimate) || 25 })
      let photosFailed = false
      if (itemPhotos.length) {
        try {
          const data = new FormData(); itemPhotos.forEach(file => data.append('images', file))
          await api.upload(`/api/v1/staff/items/${created.item.id}/images`, data)
        } catch (failure) { photosFailed = true; setError(`Dish saved, but photos failed: ${(failure as Error).message}`) }
      }
      setItemName(''); setItemDescription(''); setItemPrice(''); setItemPhotos([])
      await onChanged(); if (!photosFailed) setMessage('Dish saved to this outlet menu. Scan or refresh its table QR to see it.')
    } catch (failure) { setError((failure as Error).message) }
    finally { setBusy(false) }
  }

  return <div className="menu-studio"><div className="staff-section-head"><div><span className="staff-kicker">MENU STUDIO</span><h2>Make every dish feel special</h2><p>Categories and dishes come directly from your restaurant database. Changes appear on the guest menu after refresh.</p></div><a href={`/menu?outlet=${outlet.id}`} target="_blank" rel="noreferrer">View guest menu ↗</a></div>
    {error && <div className="staff-alert error" role="alert">{error}</div>}{message && <div className="staff-alert success" role="status">{message}</div>}
    <section className="staff-panel menu-categories-panel"><div className="staff-panel-head"><div><span className="staff-kicker">ORGANIZE</span><h2>Categories</h2></div><span className="staff-muted">{categories.length} total</span></div><div className="menu-category-list">{categories.map(([id, name]) => <div className="menu-category-card" key={id}><span className="menu-category-mark">✦</span><div><strong>{name}</strong><small>{new Set(catalogue.filter(row => row.category_id === id && row.item_id).map(row => row.item_id)).size} dishes</small></div></div>)}{!categories.length && <p>No categories yet.</p>}</div>{outlet.can_edit_brand && <form className="menu-category-form" onSubmit={createCategory}><input value={newCategory} onChange={event => setNewCategory(event.target.value)} placeholder="New category name" aria-label="New category name" required /><button className="staff-primary" disabled={busy}><Plus size={17} /> Add category</button></form>}</section>
    <div className="menu-studio-grid"><section className="staff-panel menu-create-panel"><div className="staff-panel-head"><div><span className="staff-kicker">CREATE</span><h2>Add a dish</h2></div></div>{!outlet.can_edit_brand ? <p>Only a tenant owner or manager can create brand dishes.</p> : <form className="menu-create-form" onSubmit={createItem}><label>Category<span className="menu-select-wrap"><select value={itemCategory} onChange={event => setItemCategory(event.target.value)} required><option value="">Choose a category</option>{categories.map(([id, name]) => <option key={id} value={id}>{name}</option>)}</select><ChevronDown size={17} /></span></label><label>Dish title<input value={itemName} onChange={event => setItemName(event.target.value)} placeholder="e.g. Garden bowl" required /></label><label>Description<textarea value={itemDescription} onChange={event => setItemDescription(event.target.value)} placeholder="Ingredients, flavour and what makes it special" rows={4} maxLength={800} /></label><button className="menu-ai-button" type="button" disabled={aiBusy || !itemName.trim()} onClick={() => void polish()}><Sparkles size={17} /> {aiBusy ? 'Polishing…' : 'Polish with AI'}</button><small className="menu-ai-note">Sends the title and draft to Groq. Review the suggestion before saving.</small><div className="menu-form-pair"><label>Dietary type<span className="menu-select-wrap"><select value={itemDiet} onChange={event => setItemDiet(event.target.value)}><option value="VEGETARIAN">Vegetarian</option><option value="VEGAN">Vegan</option><option value="NON_VEGETARIAN">Non-veg</option><option value="UNSPECIFIED">Other / unspecified</option></select><ChevronDown size={17} /></span></label><label>Price (₹)<input type="number" min="0" step="0.01" value={itemPrice} onChange={event => setItemPrice(event.target.value)} required placeholder="299" /></label></div><label>Estimate (minutes)<input type="number" min="0" value={itemEstimate} onChange={event => setItemEstimate(event.target.value)} /></label><label className="menu-upload-pick menu-create-upload"><ImagePlus size={17} /> Add photos<input type="file" accept="image/jpeg,image/png,image/webp" multiple onChange={event => setItemPhotos(Array.from(event.target.files || []))} /></label><small>{itemPhotos.length ? `${itemPhotos.length} photos selected` : 'Optional · up to 10 photos, 6 MB each'}</small><button className="staff-primary menu-save-button" disabled={busy || !categories.length}><Plus size={17} /> {busy ? 'Saving…' : 'Save dish'}</button></form>}</section>
      <section className="staff-panel menu-items-panel"><div className="staff-panel-head"><div><span className="staff-kicker">CURRENT CATALOGUE</span><h2>Dishes & availability</h2></div><span className="staff-muted">{items.length} dishes</span></div>{items.length ? <div className="menu-item-list">{items.map(item => <article className="menu-item-card" key={item.item_id}><div className="menu-item-head"><div><span>{item.category_name} · {item.dietary_type?.replaceAll('_', ' ').toLowerCase()}</span><strong className={`menu-visibility ${catalogue.some(row => row.item_id === item.item_id && row.offering_active && row.available) ? 'visible' : 'hidden'}`}>{catalogue.some(row => row.item_id === item.item_id && row.offering_active && row.available) ? 'Visible on guest menu' : 'Hidden from guest menu'}</strong><h3>{item.item_name}</h3><p>{item.description || 'No description yet.'}</p></div><button onClick={() => setExpandedItem(expandedItem === item.item_id ? null : item.item_id)}><ImagePlus size={17} /> Photos</button></div>{catalogue.filter(row => row.item_id === item.item_id && row.offering_id).map(row => <OfferingEditor key={row.offering_id} row={row} outletId={outlet.id} onChanged={onChanged} />)}{catalogue.filter(row => row.item_id === item.item_id && row.variant_id && !row.offering_id).map(row => <AddOffering key={row.variant_id} row={row} outletId={outlet.id} onChanged={onChanged} />)}{expandedItem === item.item_id && item.item_id && <PhotoManager itemId={item.item_id} onChanged={onChanged} />}</article>)}</div> : <div className="staff-empty compact">Add your first dish to begin.</div>}</section></div>
  </div>
}
