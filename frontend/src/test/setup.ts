import '@testing-library/jest-dom'

// Stub DOMMatrix for PDF.js in jsdom test environment
if (typeof globalThis.DOMMatrix === 'undefined') {
  // @ts-expect-error - minimal stub for test environment
  globalThis.DOMMatrix = class DOMMatrix {
    constructor() {}
    invertSelf() { return this }
  }
}

// Stub URL.createObjectURL for test environments
if (typeof URL.createObjectURL === 'undefined') {
  URL.createObjectURL = () => 'blob:mock'
}
