/// <reference types="vite/client" />

declare global {
  interface Window {
    __REVIEW_PACKAGE__?: import('./api/client').ReviewPackage
  }
}

export {}
