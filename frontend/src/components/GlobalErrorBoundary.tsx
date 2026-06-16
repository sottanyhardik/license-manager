import React from "react";

export default class GlobalErrorBoundary extends React.Component {
  state = { crashed: false };

  static getDerivedStateFromError() {
    return { crashed: true };
  }

  render() {
    if (this.state.crashed)
      return <h1>Application Error — Something broke globally.</h1>;

    return this.props.children;
  }
}
