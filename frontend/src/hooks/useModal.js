/**
 * useModal Hook
 *
 * Simple hook for managing modal open/close state.
 *
 * @example
 * const { show, open, close, toggle } = useModal();
 *
 * <button onClick={open}>Open Modal</button>
 * <Modal show={show} onHide={close}>...</Modal>
 */

import { useState, useCallback } from 'react';

export const useModal = (initialShow = false) => {
  const [show, setShow] = useState(initialShow);

  const open = useCallback(() => setShow(true), []);
  const close = useCallback(() => setShow(false), []);
  const toggle = useCallback(() => setShow(prev => !prev), []);

  return { show, open, close, toggle, setShow };
};

export default useModal;
