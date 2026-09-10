export type DraftPayload = Record<string, string | number | null>;
export type DraftRecord<T extends DraftPayload> = { id: string; version: number; payload: T; updated_at: string; expires_at: string };
export type DraftState<T extends DraftPayload> = { payload: T; record: DraftRecord<T> | null; remote: DraftRecord<T> | null; loading: boolean; initialized: boolean; saving: boolean; conflict: boolean; error: Error | null; restored: boolean };
type Transport<T extends DraftPayload> = { get: () => Promise<DraftRecord<T>>; put: (version: number, payload: T, key: string) => Promise<DraftRecord<T>>; remove: (version: number, key: string) => Promise<unknown> };
const fingerprint = (payload: DraftPayload) => JSON.stringify(Object.fromEntries(Object.entries(payload).sort(([a], [b]) => a.localeCompare(b))));
const statusIs = (error: unknown, status: number) => typeof error === "object" && error !== null && "status" in error && error.status === status;

// Only form metadata lives in this in-memory controller. Persistence belongs to the actor-scoped API.
export class DraftStore<T extends DraftPayload> {
  private state: DraftState<T>;
  private listeners = new Set<() => void>();
  private pending: Promise<boolean> | null = null;
  private retry: { signature: string; key: string } | null = null;
  private loadSequence = 0;
  constructor(private initial: T, private transport: Transport<T>, private makeKey = () => crypto.randomUUID()) {
    this.state = { payload: initial, record: null, remote: null, loading: true, initialized: false, saving: false, conflict: false, error: null, restored: false };
  }
  getSnapshot = () => this.state;
  subscribe = (listener: () => void) => { this.listeners.add(listener); return () => { this.listeners.delete(listener); }; };
  get dirty() { return fingerprint(this.state.payload) !== fingerprint(this.state.record?.payload || this.initial); }
  private patch(values: Partial<DraftState<T>>) { this.state = { ...this.state, ...values }; this.listeners.forEach(listener => listener()); }
  edit = (payload: T) => { this.patch({ payload }); };

  load = async () => {
    const sequence = ++this.loadSequence;
    this.patch({ loading: true, error: null });
    try {
      const record = await this.transport.get();
      if (sequence === this.loadSequence) { this.retry = null; this.patch({ payload: { ...this.initial, ...record.payload }, record, remote: null, initialized: true, restored: true, conflict: false }); }
    } catch (error) {
      if (sequence !== this.loadSequence) return;
      if (statusIs(error, 404)) { this.retry = null; this.patch({ payload: this.initial, record: null, remote: null, initialized: true, restored: false, conflict: false }); }
      else this.patch({ error: error as Error });
    } finally { if (sequence === this.loadSequence) this.patch({ loading: false }); }
  };

  private async conflict(error: Error) {
    this.patch({ conflict: true, error });
    try { this.patch({ remote: await this.transport.get() }); }
    catch { this.patch({ remote: null }); }
  }

  save = async (payload?: T): Promise<boolean> => {
    if (payload) this.edit(payload);
    while (this.pending) await this.pending;
    if (!this.state.initialized || this.state.loading || this.state.conflict) return false;
    if (!this.dirty) return true;
    const snapshot = this.state.payload;
    const expectedVersion = this.state.record?.version || 0;
    const signature = `${expectedVersion}:${fingerprint(snapshot)}`;
    if (this.retry?.signature !== signature) this.retry = { signature, key: this.makeKey() };
    const key = this.retry.key;
    this.patch({ saving: true, error: null });
    const operation = Promise.resolve().then(async () => {
      try {
        const record = await this.transport.put(expectedVersion, snapshot, key);
        this.retry = null;
        const untouched = fingerprint(this.state.payload) === fingerprint(snapshot);
        this.patch({ record, ...(untouched ? { payload: { ...this.initial, ...record.payload } } : {}), error: null });
        return true;
      } catch (error) {
        if (statusIs(error, 409)) await this.conflict(error as Error);
        else this.patch({ error: error as Error });
        return false;
      } finally { this.pending = null; this.patch({ saving: false }); }
    });
    this.pending = operation;
    return operation;
  };

  clear = async (): Promise<boolean> => {
    while (this.pending) await this.pending;
    if (!this.state.initialized || this.state.conflict) return false;
    const version = this.state.record?.version;
    const clearedSnapshot = this.state.payload;
    this.patch({ saving: true, error: null });
    const operation = Promise.resolve().then(async () => {
      try {
        if (version) await this.transport.remove(version, this.makeKey());
        this.retry = null;
        this.patch({ payload: fingerprint(this.state.payload) === fingerprint(clearedSnapshot) ? this.initial : this.state.payload, record: null, remote: null, restored: false, conflict: false });
        return true;
      } catch (error) {
        if (statusIs(error, 409)) await this.conflict(error as Error);
        else this.patch({ error: error as Error });
        return false;
      } finally { this.pending = null; this.patch({ saving: false }); }
    });
    this.pending = operation;
    return operation;
  };
}
