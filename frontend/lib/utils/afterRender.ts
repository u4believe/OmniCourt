/**
 * Run a callback once the current React render has finished.
 *
 * `GenLayerTransactionPanel` invokes its `onDone` callback during its own
 * render rather than from an effect. Calling `setState` straight from that
 * callback therefore updates one component while another is still rendering,
 * which React warns about ("Cannot update a component while rendering a
 * different component") and which can drop the update entirely.
 *
 * A microtask runs after the synchronous render stack unwinds but before
 * paint, so the work lands as an ordinary post-render update with no visible
 * delay.
 */
export function afterRender(callback: () => void): void {
  queueMicrotask(callback);
}
