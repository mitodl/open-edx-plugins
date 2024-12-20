// Neither the XBlock library nor SDK nor edx-platform provides any type
// information so we need to include it.
//
// 🛑 As an XBlock author, you probably should NOT edit this file. 🛑

export interface XBlockRuntime {
  handlerUrl(element: HTMLDivElement, handlerName: string, suffix?: string, query?: string): string;
  /** @deprecated XBlocks should not use children */
  children(element: HTMLDivElement): string[];

  // On Studio runtime only:
  /** Listen to a Studio event */
  listenTo?(eventName: string, callback: () => void): void;
  /** Refresh the view for the xblock represented by the specified element. */
  refreshXBlock(element: HTMLDivElement): void;
  /** Notify the Studio runtime of a client-side event */
  notify(name: 'save', data: { state: 'start', element: HTMLDivElement, message: string }): void;
  notify(name: 'save', data: { state: 'end', element: HTMLDivElement }): void;
  notify(name: 'error', data: { title: string, message: string }): void;
  notify(name: 'cancel', data: Record<never, never>): void;
  notify(name: 'modal-shown', data: any): void;
}

/**
 * Sometimes the XBlock API returns an HTMLElement wrapped in jQuery.
 * We want to discourage use of jQuery, so this is a minimal type definition
 * that just provides enough typing for you to identify and unwrap such
 * variables. See https://youmightnotneedjquery.com/
 */
export interface JQueryWrappedDiv {
  "0": HTMLDivElement;
  /** The jQuery version number */
  jquery: string;
}

export function getCsrfToken(): string {
  return document.cookie.split("; ").find((row) => row.startsWith("csrftoken="))?.split("=")[1] ?? 'unknown CSRF!';
}

/** Wraps the XBlock runtime to make it easier to use */
export class BoundRuntime {
  constructor(
    public readonly runtime: XBlockRuntime,
    public readonly element: HTMLDivElement
  ) {}

  /** GET data from a JSON handler */
  async getHandler<Data extends Record<string, any> = Record<string, any>>(handlerName: string): Promise<Data> {
    const response = await this.rawHandler(handlerName, { method: 'GET' });
    return response.json();
  }

  /** POST data to a JSON handler */
  async postHandler<Data extends Record<string, any> = Record<string, any>>(
    handlerName: string,
    data: Record<string, any> = {},
  ): Promise<Data> {
    const response = await this.rawHandler(handlerName, { method: 'POST', body: JSON.stringify(data) });
    return response.json();
  }

  /** Call an XBlock handler */
  rawHandler(handlerName: string, init: RequestInit, suffix?: string, query?: string): Promise<Response> {
    const url = this.runtime.handlerUrl(this.element, handlerName, suffix, query);
    let { headers, ...otherInit } = init;
    headers = new Headers(headers); // Wrap headers into a Headers object if not already
    if (init.method !== 'GET') {
      headers.set('X-CSRFToken', getCsrfToken());
    }
    if (!headers.has('Content-Type')) {
      headers.set('Content-Type', 'application/json');
    }
    return fetch(url, { headers, ...otherInit });
  }

  /**
   * A helper method to show a "saving..." toast while changes are being saved,
   * to handle errors, and to close the settings editor modal when complete.
   * @param savePromise
   */
  async studioSaveAndClose(savePromise: Promise<any>): Promise<void> {
    this.runtime.notify('save', { state: 'start', element: this.element, message: "Saving..." });
    try {
      await savePromise;
      this.runtime.notify('save', { state: 'end', element: this.element });
      this.runtime.notify('cancel', {});  // Close the modal
    } catch (error: unknown) {
      this.runtime.notify('error', { title: 'Failed to save changes', message: 'An error occurred.' });
      console.error(error);
    }
  }

  // To access other methods like children(), notify(), etc. use the .runtime property
}
