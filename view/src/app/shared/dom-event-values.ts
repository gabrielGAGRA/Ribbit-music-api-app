/** Reads the string value from an input, textarea, or select event target safely. */
export function readInputValue(event: Event): string {
  const { target } = event;
  if (
    typeof target === 'object' &&
    target !== null &&
    'value' in target &&
    typeof target.value === 'string'
  ) {
    return target.value;
  }
  return '';
}

/** Reads the checked state from a checkbox or radio input event target safely. */
export function readInputChecked(event: Event): boolean {
  const { target } = event;
  return (
    typeof target === 'object' &&
    target !== null &&
    'checked' in target &&
    typeof target.checked === 'boolean' &&
    target.checked
  );
}

/** Reads the selected value from a `<select>` event target safely. */
export function readSelectValue(event: Event): string {
  return readInputValue(event);
}

/** Reads the first selected `File` from a file input change event safely. */
export function readFirstSelectedFile(event: Event): File | null {
  const { target } = event;
  if (typeof target !== 'object' || target === null || !('files' in target)) {
    return null;
  }
  const { files } = target;
  if (typeof files !== 'object' || files === null || !(0 in files)) {
    return null;
  }
  const first: unknown = files[0];
  return first instanceof File ? first : null;
}

function getNamedItemFn(target: EventTarget | null): ((name: string) => unknown) | null {
  if (typeof target !== 'object' || target === null || !('elements' in target)) {
    return null;
  }
  const { elements } = target;
  if (typeof elements !== 'object' || elements === null || !('namedItem' in elements)) {
    return null;
  }
  const { namedItem } = elements;
  if (typeof namedItem !== 'function') {
    return null;
  }
  return (name: string): unknown => namedItem.call(elements, name);
}

function isMutableValueControl(value: unknown): value is { value: string } {
  return (
    typeof value === 'object' &&
    value !== null &&
    'value' in value &&
    typeof value.value === 'string'
  );
}

/** Looks up a named form control with a mutable string `value` property. */
export function readNamedFormControl(
  target: EventTarget | null,
  name: string,
): { value: string } | null {
  const namedItem = getNamedItemFn(target);
  if (!namedItem) return null;
  const control: unknown = namedItem(name);
  return isMutableValueControl(control) ? control : null;
}
