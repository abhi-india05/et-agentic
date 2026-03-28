import { useEffect, useState } from 'react'
import { useNavigate, useParams, Link } from 'react-router-dom'
import toast from 'react-hot-toast'
import { ArrowLeft, Save, Trash2, Clock, User as UserIcon } from 'lucide-react'
import { api } from '../services/api.js'
import { LoadingState, ErrorState, SectionHeader, Modal, Button } from '../components/UI.jsx'
import { fmt } from '../utils/fmt.js'

export default function ProductDetailPage() {
  const { productId } = useParams()
  const navigate = useNavigate()
  const [product, setProduct] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)
  const [saveMsg, setSaveMsg] = useState('')
  const [form, setForm] = useState({ name: '', description: '' })

  // Delete modal
  const [showDelete, setShowDelete] = useState(false)
  const [deleting, setDeleting] = useState(false)

  async function load() {
    setLoading(true)
    setError('')
    try {
      const res = await api.product(productId)
      setProduct(res)
      setForm({ name: res.name || '', description: res.description || '' })
    } catch (e) {
      setError(e.message || 'Failed to load product')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [productId]) // eslint-disable-line react-hooks/exhaustive-deps

  async function save(e) {
    e.preventDefault()
    if (!form.name.trim()) {
      setError('Product name is required')
      return
    }
    setSaving(true)
    setError('')
    setSaveMsg('')
    try {
      const updated = await api.updateProduct(productId, {
        name: form.name.trim(),
        description: form.description.trim() || null,
      })
      setProduct(updated)
      setForm({ name: updated.name || '', description: updated.description || '' })
      setSaveMsg('Saved successfully')
      toast.success('Product updated successfully')
      setTimeout(() => setSaveMsg(''), 3000)
    } catch (e) {
      setError(e.message || 'Failed to update product')
    } finally {
      setSaving(false)
    }
  }

  async function confirmDelete() {
    setDeleting(true)
    try {
      await api.deleteProduct(productId)
      toast.success('Product deleted')
      navigate('/products', { replace: true })
    } catch (e) {
      setError(e.message || 'Failed to delete product')
      setShowDelete(false)
    } finally {
      setDeleting(false)
    }
  }

  if (loading) return <LoadingState message="Loading product…" />
  if (error && !product) return <ErrorState message={error} onRetry={load} />
  if (!product) return null

  return (
    <div className="space-y-6 animate-fade-up">
      <SectionHeader
        title={product.name}
        subtitle="View and edit product details."
        action={
          <button className="btn-ghost text-xs" onClick={() => navigate(-1)}>
            <ArrowLeft className="w-4 h-4" />
            Back
          </button>
        }
      />

      {/* ─── Product Metadata ─────────────────────────────────── */}
      <div className="card">
        <div className="text-xs text-muted font-mono mb-3 uppercase tracking-wider">Details</div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-xs">
          <div>
            <span className="text-muted block mb-0.5">Product ID</span>
            <span className="text-text font-mono">{product.product_id}</span>
          </div>
          <div>
            <span className="text-muted block mb-0.5">Owner</span>
            <span className="text-text font-mono flex items-center gap-1">
              <UserIcon className="w-3 h-3" />
              {product.owner_user_id}
            </span>
          </div>
          <div>
            <span className="text-muted block mb-0.5">Created</span>
            <span className="text-text font-mono flex items-center gap-1">
              <Clock className="w-3 h-3" />
              {fmt.datetime(product.created_at)}
            </span>
          </div>
          <div>
            <span className="text-muted block mb-0.5">Updated</span>
            <span className="text-text font-mono flex items-center gap-1">
              <Clock className="w-3 h-3" />
              {fmt.reltime(product.updated_at)}
            </span>
          </div>
        </div>
        {product.is_deleted && (
          <div className="mt-3 text-xs text-danger font-mono border border-danger/20 bg-danger/5 rounded-lg px-3 py-2">
            This product was soft-deleted on {fmt.datetime(product.deleted_at)}.
          </div>
        )}
      </div>

      {/* ─── Edit Form ────────────────────────────────────────── */}
      <div className="card">
        <form onSubmit={save} className="space-y-4">
          <label className="block">
            <span className="text-xs text-muted font-mono block mb-1.5">Name *</span>
            <input
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              className="w-full bg-void border border-border rounded-lg px-3 py-2.5 text-sm text-text focus:border-accent focus:outline-none"
              maxLength={200}
            />
          </label>

          <label className="block">
            <span className="text-xs text-muted font-mono block mb-1.5">Description</span>
            <textarea
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
              className="w-full bg-void border border-border rounded-lg px-3 py-2.5 text-sm text-text focus:border-accent focus:outline-none min-h-32"
              maxLength={5000}
            />
          </label>

          {error && <div className="text-xs text-danger font-mono">{error}</div>}
          {saveMsg && <div className="text-xs text-success font-mono">{saveMsg}</div>}

          <div className="flex items-center justify-between">
            <Link to="/products" className="text-xs text-muted font-mono hover:text-text transition">
              <ArrowLeft className="w-3.5 h-3.5 inline-block mr-1" />
              All products
            </Link>
            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={() => setShowDelete(true)}
                className="btn-ghost text-xs text-danger border-danger/30 hover:bg-danger/10 hover:border-danger flex items-center gap-1.5"
              >
                <Trash2 className="w-3.5 h-3.5" />
                Delete
              </button>
              <button className="btn-primary disabled:opacity-50 flex items-center gap-2" disabled={saving}>
                <Save className="w-4 h-4" />
                {saving ? 'Saving…' : 'Save'}
              </button>
            </div>
          </div>
        </form>
      </div>

      {/* ─── Delete Confirmation Modal ────────────────────────── */}
      <Modal
        open={showDelete}
        onClose={() => setShowDelete(false)}
        title="Delete Product"
        footer={
          <>
            <Button variant="ghost" onClick={() => setShowDelete(false)} disabled={deleting}>
              Cancel
            </Button>
            <Button variant="danger" onClick={confirmDelete} disabled={deleting}>
              {deleting ? 'Deleting…' : 'Delete permanently'}
            </Button>
          </>
        }
      >
        <p>
          Are you sure you want to delete{' '}
          <strong className="text-text">{product.name}</strong>?
        </p>
        <p className="mt-2 text-xs text-muted">
          This performs a soft delete. The product will be marked as deleted but data is preserved.
        </p>
      </Modal>
    </div>
  )
}
