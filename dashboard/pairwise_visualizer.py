"""Bounded Streamlit explanation of the shared Pairwise algorithm."""

from algorithms.pairwise_minmax import pairwise_trace


def render_pairwise_visualizer():
    import streamlit as st

    st.title("Pairwise Min–Max step visualizer")
    raw = st.text_input("Prices (6–20 comma-separated finite numbers)",
                        value="8, 3, 7, 2, 9, 4")
    try:
        values = [float(item.strip()) for item in raw.split(",")]
        if not 6 <= len(values) <= 20:
            raise ValueError("enter 6–20 values")
        result, steps = pairwise_trace(values)
    except (TypeError, ValueError) as exc:
        st.warning(f"Invalid prices: {exc}")
        return
    st.write("Input array:", values)
    index = st.slider("Step", 0, len(steps) - 1, len(steps) - 1)
    step = steps[index]
    st.write("Pair indices:", step["indices"])
    st.write("Compared values:", step["pair"])
    st.write("Local smaller / larger:", step["local_min"], step["local_max"])
    a, b, c = st.columns(3)
    a.metric("Global minimum", step["minimum"])
    b.metric("Global maximum", step["maximum"])
    c.metric("Comparisons completed", step["comparisons"])
    st.caption(f"Final result: {result}. Initialization of an odd array uses one value and zero comparisons.")


if __name__ == "__main__":
    import streamlit as st
    st.set_page_config(page_title="Pairwise visualizer")
    render_pairwise_visualizer()
