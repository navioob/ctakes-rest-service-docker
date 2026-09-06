import streamlit as st
from helpers import generate_summary, generate_tags, parse_ctakes_to_json, filter_tags
import json
import streamlit_authenticator as stauth
import yaml
from yaml.loader import SafeLoader

with open('./config.yaml') as file:
    config = yaml.load(file, Loader=SafeLoader)

authenticator = stauth.Authenticate(
    config['credentials'],
    config['cookie']['name'],
    config['cookie']['key'],
    config['cookie']['expiry_days']
)

if st.session_state.get('authentication_status'):
    
    # Custom CSS for styling
    st.markdown("""
        <style>
        /* General typography and spacing */
        .stTextArea textarea {
            border: 1px solid #d0d0d0;
            border-radius: 8px;
            padding: 10px;
            font-size: 14px;
        }
        .stButton>button {
            background-color: #007bff;
            color: white;
            border-radius: 8px;
            padding: 10px 20px;
            font-weight: bold;
            float: right;
        }
        .stButton>button:hover {
            background-color: #0056b3;
        }
        .stButton>button[kind="secondary"] {
            background-color: #6c757d !important;
            color: white;
        }
        .stButton>button[kind="secondary"]:hover {
            background-color: #5a6268 !important;
        }
        .stExpander {
            border: 1px solid #e0e0d0;
            border-radius: 8px;
            margin-bottom: 10px;
        }
        .stMarkdown {
            line-height: 1.6;
        }
        h1, h2, h3 {
            color: #2c3e50;
        }
        .sidebar .stMarkdown {
            font-size: 14px;
            color: #34495e;
        }
        /* Summary div styling for light and dark modes */
        .summary-container {
            border: 1px solid #d0d0d0;
            border-radius: 8px;
            padding: 15px;
            background-color: #f5f5f5;
            color: #333333;
        }
        [data-theme="dark"] .summary-container {
            background-color: #2a2a2a;
            color: #e0e0e0;
            border-color: #4a4a4a;
        }
        /* Badge styling for terms and codes */
        .term-badge {
            display: inline-block;
            background-color: #f0f0f0;
            color: #333333;
            border-radius: 12px;
            padding: 6px 12px;
            margin: 4px 0;
            font-size: 14px;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
            vertical-align: middle;
        }
        .code-badge {
            display: inline-block;
            background-color: #007bff;
            color: white;
            border-radius: 8px;
            padding: 4px 8px;
            margin-left: 8px;
            font-size: 12px;
            vertical-align: middle;
        }
        /* Grouping container for term-code pairs */
        .pair-container {
            display: inline-block;
            background-color: #ffffff;
            border: 1px solid #e0e0e0;
            border-radius: 14px;
            padding: 4px 8px;
            margin: 4px;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
        }
        [data-theme="dark"] .pair-container {
            background-color: #2e2e2e;
            border-color: #4a4a4a;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.3);
        }
        [data-theme="dark"] .term-badge {
            background-color: #3a3a3a;
            color: #e0e0e0;
        }
        [data-theme="dark"] .code-badge {
            background-color: #0056b3;
        }
        </style>
    """, unsafe_allow_html=True)

    # Streamlit App Configuration
    st.set_page_config(
        page_title="Clinical Note Enhancer",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    # Sidebar for instructions
    with st.sidebar:
        authenticator.logout()
        st.divider()
        st.header("📋 How to Use Clinical Note Enhancer")
        st.markdown("""
        **Welcome to the Clinical Note Enhancer!**  
        This tool helps doctors transform raw clinical notes into professional summaries with SNOMED-CT code tagging.

        ### Steps to Follow
        - **Enter Clinical Notes**: Input diagnosis, symptoms, and prescription details in the provided text areas.
        - **Use Standard Abbreviations**: Include medical abbreviations (e.g., 'DM' for Diabetes Mellitus, 'od' for once daily).
        - **Submit**: Click the **Submit** button to generate an enriched summary and extract SNOMED-CT codes.
        - **Check Requirements**: Ensure the cTAKES service is running at `http://localhost:8080/ctakes-web-rest/service/analyze`.

        ### Tips
        - Provide as much detail as possible for accurate summaries.
        - Review the generated summary and codes for clinical accuracy.
        - Contact support if you encounter issues with the cTAKES service.

        **Note**: Ensure your Google API key is configured in the `.env` file.
        """, unsafe_allow_html=True)

    # Main App
    st.title("🩺 Clinical Note Enhancer")
    st.markdown("""
    Transform raw clinical notes into professionally articulated summaries and extract SNOMED-CT codes using Apache cTAKES.  
    Fill in the details below and click **Submit** to view the enriched summary and tagged codes.
    """, unsafe_allow_html=True)

    # === SESSION STATE INITIALIZATION ===
    if "doctors_text" not in st.session_state:
        st.session_state.doctors_text = ""
    if "submitted" not in st.session_state:
        st.session_state.submitted = False
    if "clear_trigger" not in st.session_state:
        st.session_state.clear_trigger = 0  # Counter to force reset

    # === HANDLE CLEAR LOGIC BEFORE WIDGETS ===
    if st.session_state.clear_trigger > 0:
        # This runs on the rerun AFTER clear button
        st.session_state.doctors_text = ""
        st.session_state.submitted = False
        st.session_state.clear_trigger = 0  # Reset trigger
        st.rerun()  # One extra rerun to fully clear UIsource 

    # === INPUT FORM ===
    # === BUTTONS ROW ===
    col_title, col_clear = st.columns([4, 1])
    with col_title:
        st.subheader("Enter Clinical Notes")
    with col_clear:
        if st.button("🗑️ Clear All Inputs", type="secondary", use_container_width=True):
            st.session_state.clear_trigger += 1  # Increment trigger
            st.rerun()  # Immediate rerun to apply clear
    with st.form(key="medical_input_form"):
        
        st.text_area(
            "Doctor's Clinical Text",
            height=150,
            placeholder="e.g., Uncontrolled DM, HPT, dyslipidemia, history of hepatitis A, currently on losartan 100mg once daily",
            help="Include current symptoms, medical history, and medication dosages.",
            key="doctors_text"
        )
        
        submit_button = st.form_submit_button("Submit", type="primary", use_container_width=True)

    

    # === PROCESS SUBMISSION ===
    if submit_button:
        st.session_state.submitted = True

    if st.session_state.submitted:
        doctors_text = st.session_state.doctors_text

        if not doctors_text:
            st.warning("Please enter at least one text field to proceed.")
        else:
            with st.spinner("Generating enriched summary and SNOMED-CT codes from clinical notes..."):
                # Call the summary endpoint
                enriched_text = generate_summary(doctors_text)
                
                if enriched_text:
                    st.subheader("📝 Enriched Clinical Summary")
                    st.markdown(f"""
                    <div class="summary-container">
                        {enriched_text}
                    </div>
                    """, unsafe_allow_html=True)
                    
                    st.divider()
                    st.subheader("🏷️ Extracted SNOMED-CT Codes")
                    
                    # Call the full pipeline via filter_tags (which now calls /generate/terms)
                    filtered_tags = filter_tags(enriched_text)
                    
                    if filtered_tags:
                        try:
                            # 1. Anatomical Sites
                            with st.expander(f'Anatomical Sites ({len(filtered_tags.get("anatomical_sites", []))})', expanded=False):
                                if filtered_tags.get("anatomical_sites"):
                                    badges = "".join([f'<div class="pair-container"><span class="term-badge">{item["term"]}</span><span class="code-badge">{item["code"]}</span></div>' 
                                                    for item in filtered_tags["anatomical_sites"]])
                                    st.markdown(badges, unsafe_allow_html=True)
                                else:
                                    st.write("No codes found.")
                            
                            # 2. Procedures
                            with st.expander(f"Procedures ({len(filtered_tags.get('procedures', []))})", expanded=False):
                                if filtered_tags.get("procedures"):
                                    badges = "".join([f'<div class="pair-container"><span class="term-badge">{item["term"]}</span><span class="code-badge">{item["code"]}</span></div>' 
                                                    for item in filtered_tags["procedures"]])
                                    st.markdown(badges, unsafe_allow_html=True)
                                else:
                                    st.write("No codes found.")
                            
                            # 3. Symptoms
                            with st.expander(f"Symptoms ({len(filtered_tags.get('symptoms', []))})", expanded=False):
                                if filtered_tags.get("symptoms"):
                                    badges = "".join([f'<div class="pair-container"><span class="term-badge">{item["term"]}</span><span class="code-badge">{item["code"]}</span></div>' 
                                                    for item in filtered_tags["symptoms"]])
                                    st.markdown(badges, unsafe_allow_html=True)
                                else:
                                    st.write("No codes found.")
                            
                            # 4. Diagnosis (Structured: Communicable & Non-Communicable)
                            diag_data = filtered_tags.get("diagnosis", {})
                            comm = diag_data.get("communicable_disease", [])
                            non_comm = diag_data.get("non_communicable_disease", [])
                            total_diag = len(comm) + len(non_comm)
                            
                            with st.expander(f"Diagnosis ({total_diag})", expanded=False):
                                if total_diag > 0:
                                    if comm:
                                        st.markdown("##### 🦠 Communicable Diseases")
                                        badges = "".join([f'<div class="pair-container"><span class="term-badge">{item["term"]}</span><span class="code-badge">{item["code"]}</span></div>' 
                                                        for item in comm])
                                        st.markdown(badges, unsafe_allow_html=True)
                                    
                                    if comm and non_comm:
                                        st.divider()
                                        
                                    if non_comm:
                                        st.markdown("##### 🏥 Non-Communicable Diseases")
                                        badges = "".join([f'<div class="pair-container"><span class="term-badge">{item["term"]}</span><span class="code-badge">{item["code"]}</span></div>' 
                                                        for item in non_comm])
                                        st.markdown(badges, unsafe_allow_html=True)
                                else:
                                    st.write("No codes found.")
                            
                            # 5. Medications
                            with st.expander(f"Medications ({len(filtered_tags.get('medications', []))})", expanded=False):
                                if filtered_tags.get("medications"):
                                    badges = "".join([f'<div class="pair-container"><span class="term-badge">{item["term"]}</span><span class="code-badge">{item["code"]}</span></div>' 
                                                    for item in filtered_tags["medications"]])
                                    st.markdown(badges, unsafe_allow_html=True)
                                else:
                                    st.write("No codes found.")
                                    
                        except Exception as e:
                            st.error(f"Error processing API output: {e}")
                    else:
                        st.error("Failed to extract SNOMED-CT terms from the service.")
                else:
                    st.error("Failed to generate enriched summary.")
                        except Exception as e:
                            st.error(f"Error parsing cTAKES output: {e}")
                    else:
                        st.error("Failed to generate tags from cTAKES.")
                else:
                    st.error("Failed to generate enriched summary.")

elif st.session_state.get('authentication_status') is False:
    st.error('Username/password is incorrect')
elif st.session_state.get('authentication_status') is None:
    authenticator.login()