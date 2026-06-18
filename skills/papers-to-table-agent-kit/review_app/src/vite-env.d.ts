/// <reference types="vite/client" />

declare global {
  interface Window {
    __REVIEW_PACKAGE__?: import('./api/client').ReviewPackage
    __REVIEW_PDF_DATA__?: Record<string, string>
    __REVIEW_PDF_DATA_INDEX__?: Record<string, string>
  }
}

export {}
