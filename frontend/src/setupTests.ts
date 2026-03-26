import '@testing-library/jest-dom'

// pdfjs-dist requires DOMMatrix and other canvas APIs not present in jsdom.
// Provide a minimal stub so tests that import components using pdfjs-dist don't crash.
// toFloat32Array/toFloat64Array return 6-element arrays matching the 2D transform matrix
// [a,b,c,d,e,f] — sufficient for 2D PDF rendering, not a full 16-element 3D matrix.
if (typeof globalThis.DOMMatrix === 'undefined') {
  class DOMMatrixStub {
    a = 1; b = 0; c = 0; d = 1; e = 0; f = 0
    is2D = true; isIdentity = true
    transformPoint() { return { x: 0, y: 0, z: 0, w: 1 } }
    translate() { return new DOMMatrixStub() }
    scale() { return new DOMMatrixStub() }
    rotate() { return new DOMMatrixStub() }
    multiply() { return new DOMMatrixStub() }
    inverse() { return new DOMMatrixStub() }
    toFloat32Array() { return new Float32Array(6) }
    toFloat64Array() { return new Float64Array(6) }
  }
  ;(globalThis as unknown as Record<string, unknown>).DOMMatrix = DOMMatrixStub
}
