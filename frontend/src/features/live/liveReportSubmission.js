export async function runLiveReportSubmission({
  inFlightRef,
  onStateChange,
  operation,
}) {
  if (inFlightRef.current) return { result: null, started: false };

  inFlightRef.current = true;
  onStateChange?.(true);
  try {
    return {
      result: await operation(),
      started: true,
    };
  } finally {
    inFlightRef.current = false;
    onStateChange?.(false);
  }
}

export function runPersistentLiveReportSubmission({
  onStateChange,
  onSuccess,
  operation,
  promiseRef,
}) {
  if (promiseRef.current) return promiseRef.current;

  onStateChange?.(true);
  const pending = Promise.resolve()
    .then(operation)
    .then(async (result) => {
      if (result?.ok) await onSuccess?.(result);
      return result;
    })
    .finally(() => {
      if (promiseRef.current === pending) promiseRef.current = null;
      onStateChange?.(false);
    });

  promiseRef.current = pending;
  return pending;
}
