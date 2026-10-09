import { useState, type FormEvent } from 'react'
import { Armchair, Plus, Trash2 } from 'lucide-react'
import StaffModal from './StaffModal'

export type DiningTable = { id: string; label: string; seating_capacity: number; active: boolean; visit_id: string | null; status: string | null; unseen_orders: number; open_requests: number }

function TableIllustration({ capacity, label }: { capacity: number; label: string }) {
  return <div className="dining-illustration" aria-label={`${capacity} seats`}>
    {Array.from({ length: capacity }, (_, index) => {
      const angle = (index / capacity) * Math.PI * 2 - Math.PI / 2
      return <span className="dining-chair" key={index} style={{ left: `${50 + Math.cos(angle) * 40}%`, top: `${50 + Math.sin(angle) * 40}%`, transform: `translate(-50%,-50%) rotate(${angle * 180 / Math.PI + 90}deg)` }}><Armchair size={19} strokeWidth={2.1} /></span>
    })}
    <span className="dining-table-top">{label}</span>
  </div>
}

export default function DiningTables({ tables, selectedId, canManage, onSelect, onCreate, onDelete, onError }: {
  tables: DiningTable[]; selectedId: string | null; canManage: boolean
  onSelect: (table: DiningTable) => void; onCreate: (label: string, capacity: number) => Promise<void>
  onDelete: (table: DiningTable) => Promise<void>; onError: (message: string) => void
}) {
  const [modalOpen, setModalOpen] = useState(false)
  const [label, setLabel] = useState('')
  const [capacity, setCapacity] = useState('4')
  const [busy, setBusy] = useState(false)
  const [showRequired, setShowRequired] = useState(false)
  async function submit(event: FormEvent) {
    event.preventDefault(); setShowRequired(true)
    const seats = Number(capacity)
    if (!label.trim() || !capacity.trim() || !Number.isInteger(seats) || seats < 1 || seats > 20) return
    setBusy(true)
    try { await onCreate(label.trim(), seats); setModalOpen(false); setLabel(''); setCapacity('4'); setShowRequired(false) }
    catch (failure) { onError((failure as Error).message) }
    finally { setBusy(false) }
  }
  return <><div className="staff-section-head"><div><span className="staff-kicker">DINING ROOM</span><h2>Your tables</h2><p>Each card shows its seating capacity. Select a table to manage its visit.</p></div>{canManage && <button className="staff-primary" onClick={() => { setShowRequired(false); setModalOpen(true) }}><Plus size={16} /> Add table</button>}</div><div className="table-grid">{tables.map(table => <article className={`table-card ${selectedId === table.id ? 'selected' : ''}`} key={table.id}><div className="table-card-top"><span className={`table-status ${table.status?.toLowerCase() || 'available'}`}>{table.status === 'CHECKOUT' ? 'Billing' : table.visit_id ? 'Dining' : 'Available'}</span>{canManage && <button className="table-delete" onClick={() => { if (window.confirm(`Remove ${table.label}? Its QR will stop working.`)) void onDelete(table) }} aria-label={`Delete ${table.label}`}><Trash2 size={15} /></button>}</div><button className="table-card-main" onClick={() => onSelect(table)}><TableIllustration capacity={table.seating_capacity} label={table.label} /><strong>{table.label}</strong><small>{table.seating_capacity} seats · {table.visit_id ? `${table.unseen_orders || 0} new orders · ${table.open_requests || 0} requests` : 'Ready for guests'}</small></button></article>)}</div>{!tables.length && <div className="staff-empty"><Armchair size={32} /><h3>No tables yet</h3><p>Add a table and its seats to create a scannable QR.</p></div>}
    {modalOpen && <StaffModal title="Add dining table" onClose={() => setModalOpen(false)}><form className="staff-dialog-form" onSubmit={submit} noValidate><label><span>Table name <span className="staff-required" aria-hidden="true">*</span></span><input value={label} onChange={event => setLabel(event.target.value)} placeholder="e.g. Table 01" maxLength={80} autoFocus required aria-invalid={showRequired && !label.trim()} />{showRequired && !label.trim() && <small className="staff-field-error">Enter a table name.</small>}</label><label><span>Seating capacity <span className="staff-required" aria-hidden="true">*</span></span><input type="number" min="1" max="20" value={capacity} onChange={event => setCapacity(event.target.value)} required aria-invalid={showRequired && (!capacity.trim() || !Number.isInteger(Number(capacity)) || Number(capacity) < 1 || Number(capacity) > 20)} />{showRequired && (!capacity.trim() || !Number.isInteger(Number(capacity)) || Number(capacity) < 1 || Number(capacity) > 20) && <small className="staff-field-error">Enter a capacity from 1 to 20.</small>}</label><div className="staff-modal-actions"><button type="button" className="staff-secondary" onClick={() => setModalOpen(false)}>Cancel</button><button className="staff-primary" disabled={busy}>{busy ? 'Saving…' : 'Save table'}</button></div></form></StaffModal>}
  </>
}
