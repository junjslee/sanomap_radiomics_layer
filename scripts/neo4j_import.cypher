// ============================================================
// SanoMap Radiomics Layer — Neo4j Import Script
// Generated from artifacts/neo4j_relationships_microbe_expanded.csv
//
// Usage — Neo4j Desktop:
//   1. Open Neo4j Desktop, start a database, open Neo4j Browser
//   2. Paste this script and run (or use cypher-shell)
//   No APOC plugin required.
// ============================================================

// Optional: clear existing graph before import
// MATCH (n) DETACH DELETE n;

// --- Constraints (deduplication) ---
CREATE CONSTRAINT bodycompositionfeature_name IF NOT EXISTS
  FOR (n:BodyCompositionFeature) REQUIRE n.name IS UNIQUE;
CREATE CONSTRAINT bodylocation_name IF NOT EXISTS
  FOR (n:BodyLocation) REQUIRE n.name IS UNIQUE;
CREATE CONSTRAINT disease_name IF NOT EXISTS
  FOR (n:Disease) REQUIRE n.name IS UNIQUE;
CREATE CONSTRAINT imageref_name IF NOT EXISTS
  FOR (n:ImageRef) REQUIRE n.name IS UNIQUE;
CREATE CONSTRAINT imagingmodality_name IF NOT EXISTS
  FOR (n:ImagingModality) REQUIRE n.name IS UNIQUE;
CREATE CONSTRAINT microbe_name IF NOT EXISTS
  FOR (n:Microbe) REQUIRE n.name IS UNIQUE;
CREATE CONSTRAINT radiomicfeature_name IF NOT EXISTS
  FOR (n:RadiomicFeature) REQUIRE n.name IS UNIQUE;

// --- Nodes ---
// BodyCompositionFeature (7 nodes)
MERGE (:BodyCompositionFeature {name: 'muscle_attenuation'});
MERGE (:BodyCompositionFeature {name: 'myosteatosis'});
MERGE (:BodyCompositionFeature {name: 'psoas_area'});
MERGE (:BodyCompositionFeature {name: 'sarcopenia'});
MERGE (:BodyCompositionFeature {name: 'skeletal_muscle_index'});
MERGE (:BodyCompositionFeature {name: 'subcutaneous_adipose_tissue'});
MERGE (:BodyCompositionFeature {name: 'visceral_adipose_tissue'});

// BodyLocation (18 nodes)
MERGE (:BodyLocation {name: 'abdomen'});
MERGE (:BodyLocation {name: 'abdominal'});
MERGE (:BodyLocation {name: 'adipose'});
MERGE (:BodyLocation {name: 'bone'});
MERGE (:BodyLocation {name: 'brain'});
MERGE (:BodyLocation {name: 'cerebral'});
MERGE (:BodyLocation {name: 'colon'});
MERGE (:BodyLocation {name: 'heart'});
MERGE (:BodyLocation {name: 'hip'});
MERGE (:BodyLocation {name: 'kidney'});
MERGE (:BodyLocation {name: 'liver'});
MERGE (:BodyLocation {name: 'lung'});
MERGE (:BodyLocation {name: 'muscle'});
MERGE (:BodyLocation {name: 'muscular'});
MERGE (:BodyLocation {name: 'rectum'});
MERGE (:BodyLocation {name: 'skeletal'});
MERGE (:BodyLocation {name: 'spleen'});
MERGE (:BodyLocation {name: 'waist'});

// Disease (30 nodes)
MERGE (:Disease {name: 'cardiovascular disease'});
MERGE (:Disease {name: 'central obesity'});
MERGE (:Disease {name: 'chronic kidney disease'});
MERGE (:Disease {name: 'chronic liver disease'});
MERGE (:Disease {name: 'cirrhosis'});
MERGE (:Disease {name: 'colon adenocarcinoma'});
MERGE (:Disease {name: 'colorectal cancer'});
MERGE (:Disease {name: 'diet-induced obesity'});
MERGE (:Disease {name: 'gallstone disease'});
MERGE (:Disease {name: 'hbs antigen-positive chronic liver disease'});
MERGE (:Disease {name: 'heart disease'});
MERGE (:Disease {name: 'hepatic fibrosis'});
MERGE (:Disease {name: 'hepatocellular carcinoma'});
MERGE (:Disease {name: 'inflammatory bowel disease'});
MERGE (:Disease {name: 'interstitial fibrosis'});
MERGE (:Disease {name: 'liver cirrhosis'});
MERGE (:Disease {name: 'liver disease'});
MERGE (:Disease {name: 'liver fibrosis'});
MERGE (:Disease {name: 'lumbar spine disease'});
MERGE (:Disease {name: 'metabolic dysfunction-associated fatty liver disease'});
MERGE (:Disease {name: 'metabolic dysfunction-associated steatotic liver disease'});
MERGE (:Disease {name: 'metabolic syndrome'});
MERGE (:Disease {name: 'metabolic-associated fatty liver disease'});
MERGE (:Disease {name: 'nonalcoholic fatty liver disease'});
MERGE (:Disease {name: 'obesity'});
MERGE (:Disease {name: 'pancreatic cancer'});
MERGE (:Disease {name: 'sarcopenic obesity'});
MERGE (:Disease {name: 'severe obesity'});
MERGE (:Disease {name: 'systemic inflammation'});
MERGE (:Disease {name: 'vat fibrosis'});

// ImageRef (1 nodes)
MERGE (:ImageRef {name: 'imageref:89b1e3b5e8a4e447'});

// ImagingModality (5 nodes)
MERGE (:ImagingModality {name: 'CT'});
MERGE (:ImagingModality {name: 'DXA'});
MERGE (:ImagingModality {name: 'MRI'});
MERGE (:ImagingModality {name: 'PET'});
MERGE (:ImagingModality {name: 'US'});

// Microbe (12 nodes)
MERGE (:Microbe {name: 'actinobacteria species'});
MERGE (:Microbe {name: 'bacteroidetes'});
MERGE (:Microbe {name: 'bifidobacterium bifidum'});
MERGE (:Microbe {name: 'bifidobacterium lactis'});
MERGE (:Microbe {name: 'catenibacterium'});
MERGE (:Microbe {name: 'dysosmobacter'});
MERGE (:Microbe {name: 'lactobacillus - based probiotics'});
MERGE (:Microbe {name: 'lactobacillus - containing probiotic'});
MERGE (:Microbe {name: 'peptostreptococcus stomatis'});
MERGE (:Microbe {name: 'prevotella_nigrescens'});
MERGE (:Microbe {name: 'proteobacteria'});
MERGE (:Microbe {name: 'ruminococcus'});

// RadiomicFeature (5 nodes)
MERGE (:RadiomicFeature {name: 'GLCM_Correlation'});
MERGE (:RadiomicFeature {name: 'first_order_kurtosis'});
MERGE (:RadiomicFeature {name: 'first_order_mean'});
MERGE (:RadiomicFeature {name: 'first_order_skewness'});
MERGE (:RadiomicFeature {name: 'glcm_homogeneity'});

// --- Relationships ---
MATCH (src:BodyCompositionFeature {name: 'subcutaneous_adipose_tissue'}), (tgt:Disease {name: 'interstitial fibrosis'}) MERGE (src)-[:ASSOCIATED_WITH {pmid: '41470854', confidence: 0.85}]->(tgt);
MATCH (src:BodyCompositionFeature {name: 'subcutaneous_adipose_tissue'}), (tgt:Disease {name: 'systemic inflammation'}) MERGE (src)-[:ASSOCIATED_WITH {pmid: '40828642', confidence: 1.0}]->(tgt);
MATCH (src:BodyCompositionFeature {name: 'sarcopenia'}), (tgt:Disease {name: 'cirrhosis'}) MERGE (src)-[:ASSOCIATED_WITH {pmid: '39539377', confidence: 0.85}]->(tgt);
MATCH (src:BodyCompositionFeature {name: 'skeletal_muscle_index'}), (tgt:Disease {name: 'metabolic-associated fatty liver disease'}) MERGE (src)-[:ASSOCIATED_WITH {pmid: '39539377', confidence: 1.0}]->(tgt);
MATCH (src:BodyCompositionFeature {name: 'sarcopenia'}), (tgt:Disease {name: 'metabolic-associated fatty liver disease'}) MERGE (src)-[:ASSOCIATED_WITH {pmid: '39539377', confidence: 1.0}]->(tgt);
MATCH (src:BodyCompositionFeature {name: 'sarcopenia'}), (tgt:Disease {name: 'metabolic syndrome'}) MERGE (src)-[:ASSOCIATED_WITH {pmid: '36651482', confidence: 1.0}]->(tgt);
MATCH (src:BodyCompositionFeature {name: 'subcutaneous_adipose_tissue'}), (tgt:Disease {name: 'colorectal cancer'}) MERGE (src)-[:ASSOCIATED_WITH {pmid: '36549742', confidence: 1.0}]->(tgt);
MATCH (src:BodyCompositionFeature {name: 'visceral_adipose_tissue'}), (tgt:Disease {name: 'colorectal cancer'}) MERGE (src)-[:ASSOCIATED_WITH {pmid: '34871345', confidence: 1.0}]->(tgt);
MATCH (src:BodyCompositionFeature {name: 'skeletal_muscle_index'}), (tgt:Disease {name: 'metabolic dysfunction-associated fatty liver disease'}) MERGE (src)-[:ASSOCIATED_WITH {pmid: '33436764', confidence: 1.0}]->(tgt);
MATCH (src:BodyCompositionFeature {name: 'muscle_attenuation'}), (tgt:Disease {name: 'colorectal cancer'}) MERGE (src)-[:ASSOCIATED_WITH {pmid: '24886284', confidence: 1.0}]->(tgt);
MATCH (src:BodyCompositionFeature {name: 'sarcopenia'}), (tgt:Disease {name: 'cirrhosis'}) MERGE (src)-[:ASSOCIATED_WITH {pmid: '41561025', confidence: 0.85}]->(tgt);
MATCH (src:BodyCompositionFeature {name: 'sarcopenia'}), (tgt:Disease {name: 'chronic kidney disease'}) MERGE (src)-[:ASSOCIATED_WITH {pmid: '41516422', confidence: 1.0}]->(tgt);
MATCH (src:BodyCompositionFeature {name: 'sarcopenia'}), (tgt:Disease {name: 'metabolic syndrome'}) MERGE (src)-[:ASSOCIATED_WITH {pmid: '41312308', confidence: 0.7}]->(tgt);
MATCH (src:BodyCompositionFeature {name: 'sarcopenia'}), (tgt:Disease {name: 'lumbar spine disease'}) MERGE (src)-[:ASSOCIATED_WITH {pmid: '41312308', confidence: 1.0}]->(tgt);
MATCH (src:BodyCompositionFeature {name: 'sarcopenia'}), (tgt:Disease {name: 'sarcopenic obesity'}) MERGE (src)-[:ASSOCIATED_WITH {pmid: '41097233', confidence: 0.85}]->(tgt);
MATCH (src:BodyCompositionFeature {name: 'sarcopenia'}), (tgt:Disease {name: 'liver disease'}) MERGE (src)-[:ASSOCIATED_WITH {pmid: '40901602', confidence: 1.0}]->(tgt);
MATCH (src:BodyCompositionFeature {name: 'sarcopenia'}), (tgt:Disease {name: 'systemic inflammation'}) MERGE (src)-[:ASSOCIATED_WITH {pmid: '40901602', confidence: 0.85}]->(tgt);
MATCH (src:BodyCompositionFeature {name: 'sarcopenia'}), (tgt:Disease {name: 'cirrhosis'}) MERGE (src)-[:ASSOCIATED_WITH {pmid: '40901602', confidence: 1.0}]->(tgt);
MATCH (src:BodyCompositionFeature {name: 'sarcopenia'}), (tgt:Disease {name: 'cardiovascular disease'}) MERGE (src)-[:ASSOCIATED_WITH {pmid: '40901292', confidence: 0.85}]->(tgt);
MATCH (src:BodyCompositionFeature {name: 'sarcopenia'}), (tgt:Disease {name: 'metabolic dysfunction-associated steatotic liver disease'}) MERGE (src)-[:ASSOCIATED_WITH {pmid: '40847308', confidence: 1.0}]->(tgt);
MATCH (src:BodyCompositionFeature {name: 'sarcopenia'}), (tgt:Disease {name: 'colorectal cancer'}) MERGE (src)-[:ASSOCIATED_WITH {pmid: '40847308', confidence: 0.85}]->(tgt);
MATCH (src:BodyCompositionFeature {name: 'visceral_adipose_tissue'}), (tgt:Disease {name: 'inflammatory bowel disease'}) MERGE (src)-[:ASSOCIATED_WITH {pmid: '40575928', confidence: 1.0}]->(tgt);
MATCH (src:BodyCompositionFeature {name: 'sarcopenia'}), (tgt:Disease {name: 'sarcopenic obesity'}) MERGE (src)-[:ASSOCIATED_WITH {pmid: '40511533', confidence: 0.85}]->(tgt);
MATCH (src:BodyCompositionFeature {name: 'sarcopenia'}), (tgt:Disease {name: 'nonalcoholic fatty liver disease'}) MERGE (src)-[:ASSOCIATED_WITH {pmid: '40494999', confidence: 1.0}]->(tgt);
MATCH (src:BodyCompositionFeature {name: 'visceral_adipose_tissue'}), (tgt:Disease {name: 'hepatic fibrosis'}) MERGE (src)-[:ASSOCIATED_WITH {pmid: '40116510', confidence: 0.85}]->(tgt);
MATCH (src:BodyCompositionFeature {name: 'sarcopenia'}), (tgt:Disease {name: 'hepatic fibrosis'}) MERGE (src)-[:ASSOCIATED_WITH {pmid: '40116510', confidence: 0.85}]->(tgt);
MATCH (src:BodyCompositionFeature {name: 'visceral_adipose_tissue'}), (tgt:Disease {name: 'obesity'}) MERGE (src)-[:ASSOCIATED_WITH {pmid: '39998325', confidence: 0.85}]->(tgt);
MATCH (src:BodyCompositionFeature {name: 'myosteatosis'}), (tgt:Disease {name: 'liver cirrhosis'}) MERGE (src)-[:ASSOCIATED_WITH {pmid: '39968394', confidence: 0.85}]->(tgt);
MATCH (src:BodyCompositionFeature {name: 'visceral_adipose_tissue'}), (tgt:Disease {name: 'obesity'}) MERGE (src)-[:ASSOCIATED_WITH {pmid: '39617894', confidence: 0.85}]->(tgt);
MATCH (src:BodyCompositionFeature {name: 'sarcopenia'}), (tgt:Disease {name: 'metabolic syndrome'}) MERGE (src)-[:ASSOCIATED_WITH {pmid: '39408262', confidence: 0.7}]->(tgt);
MATCH (src:BodyCompositionFeature {name: 'sarcopenia'}), (tgt:Disease {name: 'metabolic syndrome'}) MERGE (src)-[:ASSOCIATED_WITH {pmid: '38995073', confidence: 0.85}]->(tgt);
MATCH (src:BodyCompositionFeature {name: 'visceral_adipose_tissue'}), (tgt:Disease {name: 'colon adenocarcinoma'}) MERGE (src)-[:ASSOCIATED_WITH {pmid: '38937454', confidence: 0.85}]->(tgt);
MATCH (src:BodyCompositionFeature {name: 'skeletal_muscle_index'}), (tgt:Disease {name: 'systemic inflammation'}) MERGE (src)-[:ASSOCIATED_WITH {pmid: '38140308', confidence: 0.85}]->(tgt);
MATCH (src:BodyCompositionFeature {name: 'sarcopenia'}), (tgt:Disease {name: 'systemic inflammation'}) MERGE (src)-[:ASSOCIATED_WITH {pmid: '38140308', confidence: 0.85}]->(tgt);
MATCH (src:BodyCompositionFeature {name: 'subcutaneous_adipose_tissue'}), (tgt:Disease {name: 'liver fibrosis'}) MERGE (src)-[:ASSOCIATED_WITH {pmid: '38101770', confidence: 1.0}]->(tgt);
MATCH (src:BodyCompositionFeature {name: 'visceral_adipose_tissue'}), (tgt:Disease {name: 'obesity'}) MERGE (src)-[:ASSOCIATED_WITH {pmid: '37836532', confidence: 0.85}]->(tgt);
MATCH (src:BodyCompositionFeature {name: 'sarcopenia'}), (tgt:Disease {name: 'cirrhosis'}) MERGE (src)-[:ASSOCIATED_WITH {pmid: '37767786', confidence: 1.0}]->(tgt);
MATCH (src:BodyCompositionFeature {name: 'sarcopenia'}), (tgt:Disease {name: 'colorectal cancer'}) MERGE (src)-[:ASSOCIATED_WITH {pmid: '37767786', confidence: 0.85}]->(tgt);
MATCH (src:BodyCompositionFeature {name: 'visceral_adipose_tissue'}), (tgt:Disease {name: 'metabolic-associated fatty liver disease'}) MERGE (src)-[:ASSOCIATED_WITH {pmid: '37495346', confidence: 0.7}]->(tgt);
MATCH (src:BodyCompositionFeature {name: 'sarcopenia'}), (tgt:Disease {name: 'metabolic-associated fatty liver disease'}) MERGE (src)-[:ASSOCIATED_WITH {pmid: '37495346', confidence: 0.7}]->(tgt);
MATCH (src:BodyCompositionFeature {name: 'visceral_adipose_tissue'}), (tgt:Disease {name: 'central obesity'}) MERGE (src)-[:ASSOCIATED_WITH {pmid: '36794912', confidence: 1.0}]->(tgt);
MATCH (src:BodyCompositionFeature {name: 'subcutaneous_adipose_tissue'}), (tgt:Disease {name: 'central obesity'}) MERGE (src)-[:ASSOCIATED_WITH {pmid: '36794912', confidence: 1.0}]->(tgt);
MATCH (src:BodyCompositionFeature {name: 'sarcopenia'}), (tgt:Disease {name: 'cirrhosis'}) MERGE (src)-[:ASSOCIATED_WITH {pmid: '36536957', confidence: 0.9}]->(tgt);
MATCH (src:BodyCompositionFeature {name: 'sarcopenia'}), (tgt:Disease {name: 'sarcopenic obesity'}) MERGE (src)-[:ASSOCIATED_WITH {pmid: '36338472', confidence: 1.0}]->(tgt);
MATCH (src:BodyCompositionFeature {name: 'subcutaneous_adipose_tissue'}), (tgt:Disease {name: 'gallstone disease'}) MERGE (src)-[:ASSOCIATED_WITH {pmid: '36115596', confidence: 1.0}]->(tgt);
MATCH (src:BodyCompositionFeature {name: 'visceral_adipose_tissue'}), (tgt:Disease {name: 'gallstone disease'}) MERGE (src)-[:ASSOCIATED_WITH {pmid: '36115596', confidence: 1.0}]->(tgt);
MATCH (src:BodyCompositionFeature {name: 'sarcopenia'}), (tgt:Disease {name: 'chronic kidney disease'}) MERGE (src)-[:ASSOCIATED_WITH {pmid: '36090199', confidence: 1.0}]->(tgt);
MATCH (src:BodyCompositionFeature {name: 'sarcopenia'}), (tgt:Disease {name: 'cirrhosis'}) MERGE (src)-[:ASSOCIATED_WITH {pmid: '35978666', confidence: 1.0}]->(tgt);
MATCH (src:BodyCompositionFeature {name: 'sarcopenia'}), (tgt:Disease {name: 'heart disease'}) MERGE (src)-[:ASSOCIATED_WITH {pmid: '35891702', confidence: 0.85}]->(tgt);
MATCH (src:BodyCompositionFeature {name: 'visceral_adipose_tissue'}), (tgt:Disease {name: 'vat fibrosis'}) MERGE (src)-[:ASSOCIATED_WITH {pmid: '35848617', confidence: 0.85}]->(tgt);
MATCH (src:BodyCompositionFeature {name: 'sarcopenia'}), (tgt:Disease {name: 'chronic liver disease'}) MERGE (src)-[:ASSOCIATED_WITH {pmid: '35256716', confidence: 1.0}]->(tgt);
MATCH (src:BodyCompositionFeature {name: 'skeletal_muscle_index'}), (tgt:Disease {name: 'chronic liver disease'}) MERGE (src)-[:ASSOCIATED_WITH {pmid: '35256716', confidence: 1.0}]->(tgt);
MATCH (src:BodyCompositionFeature {name: 'skeletal_muscle_index'}), (tgt:Disease {name: 'hepatocellular carcinoma'}) MERGE (src)-[:ASSOCIATED_WITH {pmid: '35256716', confidence: 1.0}]->(tgt);
MATCH (src:BodyCompositionFeature {name: 'skeletal_muscle_index'}), (tgt:Disease {name: 'hbs antigen-positive chronic liver disease'}) MERGE (src)-[:ASSOCIATED_WITH {pmid: '35256716', confidence: 1.0}]->(tgt);
MATCH (src:BodyCompositionFeature {name: 'skeletal_muscle_index'}), (tgt:Disease {name: 'liver disease'}) MERGE (src)-[:ASSOCIATED_WITH {pmid: '35256716', confidence: 0.85}]->(tgt);
MATCH (src:BodyCompositionFeature {name: 'sarcopenia'}), (tgt:Disease {name: 'liver disease'}) MERGE (src)-[:ASSOCIATED_WITH {pmid: '35256716', confidence: 0.85}]->(tgt);
MATCH (src:BodyCompositionFeature {name: 'visceral_adipose_tissue'}), (tgt:Disease {name: 'obesity'}) MERGE (src)-[:ASSOCIATED_WITH {pmid: '35127122', confidence: 1.0}]->(tgt);
MATCH (src:BodyCompositionFeature {name: 'subcutaneous_adipose_tissue'}), (tgt:Disease {name: 'pancreatic cancer'}) MERGE (src)-[:ASSOCIATED_WITH {pmid: '34737977', confidence: 0.85}]->(tgt);
MATCH (src:BodyCompositionFeature {name: 'visceral_adipose_tissue'}), (tgt:Disease {name: 'pancreatic cancer'}) MERGE (src)-[:ASSOCIATED_WITH {pmid: '34737977', confidence: 0.85}]->(tgt);
MATCH (src:BodyCompositionFeature {name: 'sarcopenia'}), (tgt:Disease {name: 'chronic kidney disease'}) MERGE (src)-[:ASSOCIATED_WITH {pmid: '34357944', confidence: 1.0}]->(tgt);
MATCH (src:BodyCompositionFeature {name: 'sarcopenia'}), (tgt:Disease {name: 'systemic inflammation'}) MERGE (src)-[:ASSOCIATED_WITH {pmid: '34357944', confidence: 0.85}]->(tgt);
MATCH (src:BodyCompositionFeature {name: 'visceral_adipose_tissue'}), (tgt:Disease {name: 'metabolic syndrome'}) MERGE (src)-[:ASSOCIATED_WITH {pmid: '34315463', confidence: 1.0}]->(tgt);
MATCH (src:BodyCompositionFeature {name: 'sarcopenia'}), (tgt:Disease {name: 'liver cirrhosis'}) MERGE (src)-[:ASSOCIATED_WITH {pmid: '33348106', confidence: 0.85}]->(tgt);
MATCH (src:BodyCompositionFeature {name: 'sarcopenia'}), (tgt:Disease {name: 'inflammatory bowel disease'}) MERGE (src)-[:ASSOCIATED_WITH {pmid: '33255677', confidence: 0.9}]->(tgt);
MATCH (src:BodyCompositionFeature {name: 'sarcopenia'}), (tgt:Disease {name: 'chronic kidney disease'}) MERGE (src)-[:ASSOCIATED_WITH {pmid: '32535631', confidence: 0.85}]->(tgt);
MATCH (src:BodyCompositionFeature {name: 'visceral_adipose_tissue'}), (tgt:Disease {name: 'systemic inflammation'}) MERGE (src)-[:ASSOCIATED_WITH {pmid: '31809363', confidence: 0.9}]->(tgt);
MATCH (src:BodyCompositionFeature {name: 'subcutaneous_adipose_tissue'}), (tgt:Disease {name: 'diet-induced obesity'}) MERGE (src)-[:ASSOCIATED_WITH {pmid: '31611297', confidence: 1.0}]->(tgt);
MATCH (src:BodyCompositionFeature {name: 'visceral_adipose_tissue'}), (tgt:Disease {name: 'obesity'}) MERGE (src)-[:ASSOCIATED_WITH {pmid: '31333715', confidence: 1.0}]->(tgt);
MATCH (src:BodyCompositionFeature {name: 'visceral_adipose_tissue'}), (tgt:Disease {name: 'severe obesity'}) MERGE (src)-[:ASSOCIATED_WITH {pmid: '29899081', confidence: 0.85}]->(tgt);
MATCH (src:BodyCompositionFeature {name: 'sarcopenia'}), (tgt:Disease {name: 'sarcopenic obesity'}) MERGE (src)-[:ASSOCIATED_WITH {pmid: '23396869', confidence: 0.7}]->(tgt);
MATCH (src:BodyCompositionFeature {name: 'visceral_adipose_tissue'}), (tgt:Disease {name: 'colorectal cancer'}) MERGE (src)-[:ASSOCIATED_WITH {pmid: '23396869', confidence: 0.85}]->(tgt);
MATCH (src:BodyCompositionFeature {name: 'sarcopenia'}), (tgt:Disease {name: 'colorectal cancer'}) MERGE (src)-[:ASSOCIATED_WITH {pmid: '23396869', confidence: 1.0}]->(tgt);
MATCH (src:Microbe {name: 'prevotella_nigrescens'}), (tgt:RadiomicFeature {name: 'GLCM_Correlation'}) MERGE (src)-[:CORRELATES_WITH {confidence: 1.0}]->(tgt);
MATCH (src:RadiomicFeature {name: 'glcm_homogeneity'}), (tgt:BodyLocation {name: 'cerebral'}) MERGE (src)-[:MEASURED_AT {pmid: '39613905'}]->(tgt);
MATCH (src:RadiomicFeature {name: 'glcm_homogeneity'}), (tgt:ImagingModality {name: 'CT'}) MERGE (src)-[:ACQUIRED_VIA {pmid: '39613905'}]->(tgt);
MATCH (src:RadiomicFeature {name: 'first_order_kurtosis'}), (tgt:BodyLocation {name: 'cerebral'}) MERGE (src)-[:MEASURED_AT {pmid: '39613905'}]->(tgt);
MATCH (src:RadiomicFeature {name: 'first_order_kurtosis'}), (tgt:ImagingModality {name: 'CT'}) MERGE (src)-[:ACQUIRED_VIA {pmid: '39613905'}]->(tgt);
MATCH (src:RadiomicFeature {name: 'glcm_homogeneity'}), (tgt:BodyLocation {name: 'brain'}) MERGE (src)-[:MEASURED_AT {pmid: '39613905'}]->(tgt);
MATCH (src:RadiomicFeature {name: 'first_order_kurtosis'}), (tgt:BodyLocation {name: 'brain'}) MERGE (src)-[:MEASURED_AT {pmid: '39613905'}]->(tgt);
MATCH (src:BodyCompositionFeature {name: 'visceral_adipose_tissue'}), (tgt:ImagingModality {name: 'CT'}) MERGE (src)-[:ACQUIRED_VIA {pmid: '41731631'}]->(tgt);
MATCH (src:BodyCompositionFeature {name: 'visceral_adipose_tissue'}), (tgt:BodyLocation {name: 'adipose'}) MERGE (src)-[:MEASURED_AT {pmid: '41731631'}]->(tgt);
MATCH (src:BodyCompositionFeature {name: 'sarcopenia'}), (tgt:BodyLocation {name: 'muscle'}) MERGE (src)-[:MEASURED_AT {pmid: '41547903'}]->(tgt);
MATCH (src:BodyCompositionFeature {name: 'sarcopenia'}), (tgt:ImagingModality {name: 'CT'}) MERGE (src)-[:ACQUIRED_VIA {pmid: '41547903'}]->(tgt);
MATCH (src:BodyCompositionFeature {name: 'skeletal_muscle_index'}), (tgt:BodyLocation {name: 'muscle'}) MERGE (src)-[:MEASURED_AT {pmid: '41547903'}]->(tgt);
MATCH (src:BodyCompositionFeature {name: 'skeletal_muscle_index'}), (tgt:ImagingModality {name: 'CT'}) MERGE (src)-[:ACQUIRED_VIA {pmid: '41547903'}]->(tgt);
MATCH (src:BodyCompositionFeature {name: 'sarcopenia'}), (tgt:BodyLocation {name: 'bone'}) MERGE (src)-[:MEASURED_AT {pmid: '41547903'}]->(tgt);
MATCH (src:BodyCompositionFeature {name: 'visceral_adipose_tissue'}), (tgt:ImagingModality {name: 'DXA'}) MERGE (src)-[:ACQUIRED_VIA {pmid: '41512635'}]->(tgt);
MATCH (src:BodyCompositionFeature {name: 'subcutaneous_adipose_tissue'}), (tgt:BodyLocation {name: 'adipose'}) MERGE (src)-[:MEASURED_AT {pmid: '41512635'}]->(tgt);
MATCH (src:BodyCompositionFeature {name: 'subcutaneous_adipose_tissue'}), (tgt:ImagingModality {name: 'CT'}) MERGE (src)-[:ACQUIRED_VIA {pmid: '41470854'}]->(tgt);
MATCH (src:BodyCompositionFeature {name: 'subcutaneous_adipose_tissue'}), (tgt:BodyLocation {name: 'muscle'}) MERGE (src)-[:MEASURED_AT {pmid: '41470854'}]->(tgt);
MATCH (src:BodyCompositionFeature {name: 'skeletal_muscle_index'}), (tgt:BodyLocation {name: 'kidney'}) MERGE (src)-[:MEASURED_AT {pmid: '41199947'}]->(tgt);
MATCH (src:BodyCompositionFeature {name: 'sarcopenia'}), (tgt:BodyLocation {name: 'kidney'}) MERGE (src)-[:MEASURED_AT {pmid: '41199947'}]->(tgt);
MATCH (src:RadiomicFeature {name: 'first_order_mean'}), (tgt:BodyLocation {name: 'liver'}) MERGE (src)-[:MEASURED_AT {pmid: '40806015'}]->(tgt);
MATCH (src:BodyCompositionFeature {name: 'subcutaneous_adipose_tissue'}), (tgt:BodyLocation {name: 'abdominal'}) MERGE (src)-[:MEASURED_AT {pmid: '40342635'}]->(tgt);
MATCH (src:BodyCompositionFeature {name: 'sarcopenia'}), (tgt:ImagingModality {name: 'DXA'}) MERGE (src)-[:ACQUIRED_VIA {pmid: '40191209'}]->(tgt);
MATCH (src:BodyCompositionFeature {name: 'skeletal_muscle_index'}), (tgt:BodyLocation {name: 'abdominal'}) MERGE (src)-[:MEASURED_AT {pmid: '39539377'}]->(tgt);
MATCH (src:BodyCompositionFeature {name: 'sarcopenia'}), (tgt:BodyLocation {name: 'abdominal'}) MERGE (src)-[:MEASURED_AT {pmid: '39539377'}]->(tgt);
MATCH (src:BodyCompositionFeature {name: 'skeletal_muscle_index'}), (tgt:BodyLocation {name: 'liver'}) MERGE (src)-[:MEASURED_AT {pmid: '39539377'}]->(tgt);
MATCH (src:BodyCompositionFeature {name: 'sarcopenia'}), (tgt:BodyLocation {name: 'liver'}) MERGE (src)-[:MEASURED_AT {pmid: '39539377'}]->(tgt);
MATCH (src:BodyCompositionFeature {name: 'skeletal_muscle_index'}), (tgt:BodyLocation {name: 'skeletal'}) MERGE (src)-[:MEASURED_AT {pmid: '39539377'}]->(tgt);
MATCH (src:BodyCompositionFeature {name: 'sarcopenia'}), (tgt:ImagingModality {name: 'PET'}) MERGE (src)-[:ACQUIRED_VIA {pmid: '39539377'}]->(tgt);
MATCH (src:BodyCompositionFeature {name: 'visceral_adipose_tissue'}), (tgt:BodyLocation {name: 'abdominal'}) MERGE (src)-[:MEASURED_AT {pmid: '39367431'}]->(tgt);
MATCH (src:BodyCompositionFeature {name: 'subcutaneous_adipose_tissue'}), (tgt:ImagingModality {name: 'DXA'}) MERGE (src)-[:ACQUIRED_VIA {pmid: '39367431'}]->(tgt);
MATCH (src:BodyCompositionFeature {name: 'visceral_adipose_tissue'}), (tgt:BodyLocation {name: 'waist'}) MERGE (src)-[:MEASURED_AT {pmid: '39367431'}]->(tgt);
MATCH (src:BodyCompositionFeature {name: 'visceral_adipose_tissue'}), (tgt:BodyLocation {name: 'muscle'}) MERGE (src)-[:MEASURED_AT {pmid: '37935884'}]->(tgt);
MATCH (src:BodyCompositionFeature {name: 'visceral_adipose_tissue'}), (tgt:BodyLocation {name: 'liver'}) MERGE (src)-[:MEASURED_AT {pmid: '37926191'}]->(tgt);
MATCH (src:BodyCompositionFeature {name: 'subcutaneous_adipose_tissue'}), (tgt:BodyLocation {name: 'liver'}) MERGE (src)-[:MEASURED_AT {pmid: '37926191'}]->(tgt);
MATCH (src:BodyCompositionFeature {name: 'subcutaneous_adipose_tissue'}), (tgt:ImagingModality {name: 'MRI'}) MERGE (src)-[:ACQUIRED_VIA {pmid: '37926191'}]->(tgt);
MATCH (src:BodyCompositionFeature {name: 'visceral_adipose_tissue'}), (tgt:ImagingModality {name: 'MRI'}) MERGE (src)-[:ACQUIRED_VIA {pmid: '37926191'}]->(tgt);
MATCH (src:BodyCompositionFeature {name: 'sarcopenia'}), (tgt:BodyLocation {name: 'skeletal'}) MERGE (src)-[:MEASURED_AT {pmid: '37591518'}]->(tgt);
MATCH (src:BodyCompositionFeature {name: 'subcutaneous_adipose_tissue'}), (tgt:BodyLocation {name: 'waist'}) MERGE (src)-[:MEASURED_AT {pmid: '36402008'}]->(tgt);
MATCH (src:BodyCompositionFeature {name: 'skeletal_muscle_index'}), (tgt:BodyLocation {name: 'waist'}) MERGE (src)-[:MEASURED_AT {pmid: '36246928'}]->(tgt);
MATCH (src:RadiomicFeature {name: 'first_order_mean'}), (tgt:ImagingModality {name: 'CT'}) MERGE (src)-[:ACQUIRED_VIA {pmid: '34555041'}]->(tgt);
MATCH (src:BodyCompositionFeature {name: 'visceral_adipose_tissue'}), (tgt:BodyLocation {name: 'heart'}) MERGE (src)-[:MEASURED_AT {pmid: '34467673'}]->(tgt);
MATCH (src:BodyCompositionFeature {name: 'skeletal_muscle_index'}), (tgt:BodyLocation {name: 'adipose'}) MERGE (src)-[:MEASURED_AT {pmid: '33557667'}]->(tgt);
MATCH (src:BodyCompositionFeature {name: 'skeletal_muscle_index'}), (tgt:ImagingModality {name: 'DXA'}) MERGE (src)-[:ACQUIRED_VIA {pmid: '33557667'}]->(tgt);
MATCH (src:BodyCompositionFeature {name: 'myosteatosis'}), (tgt:ImagingModality {name: 'CT'}) MERGE (src)-[:ACQUIRED_VIA {pmid: '33436764'}]->(tgt);
MATCH (src:BodyCompositionFeature {name: 'myosteatosis'}), (tgt:BodyLocation {name: 'liver'}) MERGE (src)-[:MEASURED_AT {pmid: '33436764'}]->(tgt);
MATCH (src:BodyCompositionFeature {name: 'myosteatosis'}), (tgt:BodyLocation {name: 'muscle'}) MERGE (src)-[:MEASURED_AT {pmid: '33436764'}]->(tgt);
MATCH (src:BodyCompositionFeature {name: 'muscle_attenuation'}), (tgt:BodyLocation {name: 'liver'}) MERGE (src)-[:MEASURED_AT {pmid: '33436764'}]->(tgt);
MATCH (src:BodyCompositionFeature {name: 'sarcopenia'}), (tgt:BodyLocation {name: 'colon'}) MERGE (src)-[:MEASURED_AT {pmid: '31053143'}]->(tgt);
MATCH (src:BodyCompositionFeature {name: 'muscle_attenuation'}), (tgt:BodyLocation {name: 'muscle'}) MERGE (src)-[:MEASURED_AT {pmid: '24886284'}]->(tgt);
MATCH (src:BodyCompositionFeature {name: 'muscle_attenuation'}), (tgt:ImagingModality {name: 'CT'}) MERGE (src)-[:ACQUIRED_VIA {pmid: '24886284'}]->(tgt);
MATCH (src:RadiomicFeature {name: 'glcm_homogeneity'}), (tgt:BodyLocation {name: 'waist'}) MERGE (src)-[:MEASURED_AT {pmid: '41751175'}]->(tgt);
MATCH (src:BodyCompositionFeature {name: 'sarcopenia'}), (tgt:BodyLocation {name: 'heart'}) MERGE (src)-[:MEASURED_AT {pmid: '41516422'}]->(tgt);
MATCH (src:BodyCompositionFeature {name: 'sarcopenia'}), (tgt:BodyLocation {name: 'cerebral'}) MERGE (src)-[:MEASURED_AT {pmid: '41312308'}]->(tgt);
MATCH (src:BodyCompositionFeature {name: 'skeletal_muscle_index'}), (tgt:BodyLocation {name: 'bone'}) MERGE (src)-[:MEASURED_AT {pmid: '41312308'}]->(tgt);
MATCH (src:BodyCompositionFeature {name: 'sarcopenia'}), (tgt:BodyLocation {name: 'muscular'}) MERGE (src)-[:MEASURED_AT {pmid: '41312308'}]->(tgt);
MATCH (src:RadiomicFeature {name: 'first_order_mean'}), (tgt:BodyLocation {name: 'muscle'}) MERGE (src)-[:MEASURED_AT {pmid: '41097233'}]->(tgt);
MATCH (src:BodyCompositionFeature {name: 'visceral_adipose_tissue'}), (tgt:BodyLocation {name: 'brain'}) MERGE (src)-[:MEASURED_AT {pmid: '40863567'}]->(tgt);
MATCH (src:RadiomicFeature {name: 'first_order_skewness'}), (tgt:ImagingModality {name: 'CT'}) MERGE (src)-[:ACQUIRED_VIA {pmid: '40863567'}]->(tgt);
MATCH (src:RadiomicFeature {name: 'first_order_skewness'}), (tgt:BodyLocation {name: 'liver'}) MERGE (src)-[:MEASURED_AT {pmid: '40863141'}]->(tgt);
MATCH (src:BodyCompositionFeature {name: 'sarcopenia'}), (tgt:BodyLocation {name: 'rectum'}) MERGE (src)-[:MEASURED_AT {pmid: '40494999'}]->(tgt);
MATCH (src:BodyCompositionFeature {name: 'psoas_area'}), (tgt:BodyLocation {name: 'muscle'}) MERGE (src)-[:MEASURED_AT {pmid: '40095615'}]->(tgt);
MATCH (src:BodyCompositionFeature {name: 'psoas_area'}), (tgt:ImagingModality {name: 'CT'}) MERGE (src)-[:ACQUIRED_VIA {pmid: '40095615'}]->(tgt);
MATCH (src:BodyCompositionFeature {name: 'visceral_adipose_tissue'}), (tgt:BodyLocation {name: 'spleen'}) MERGE (src)-[:MEASURED_AT {pmid: '39998325'}]->(tgt);
MATCH (src:BodyCompositionFeature {name: 'sarcopenia'}), (tgt:BodyLocation {name: 'hip'}) MERGE (src)-[:MEASURED_AT {pmid: '39829204'}]->(tgt);
MATCH (src:BodyCompositionFeature {name: 'visceral_adipose_tissue'}), (tgt:BodyLocation {name: 'colon'}) MERGE (src)-[:MEASURED_AT {pmid: '39754121'}]->(tgt);
MATCH (src:BodyCompositionFeature {name: 'visceral_adipose_tissue'}), (tgt:BodyLocation {name: 'abdomen'}) MERGE (src)-[:MEASURED_AT {pmid: '39163971'}]->(tgt);
MATCH (src:BodyCompositionFeature {name: 'visceral_adipose_tissue'}), (tgt:BodyLocation {name: 'lung'}) MERGE (src)-[:MEASURED_AT {pmid: '38937454'}]->(tgt);
MATCH (src:RadiomicFeature {name: 'glcm_homogeneity'}), (tgt:BodyLocation {name: 'liver'}) MERGE (src)-[:MEASURED_AT {pmid: '38556870'}]->(tgt);
MATCH (src:BodyCompositionFeature {name: 'sarcopenia'}), (tgt:BodyLocation {name: 'brain'}) MERGE (src)-[:MEASURED_AT {pmid: '38315140'}]->(tgt);
MATCH (src:BodyCompositionFeature {name: 'skeletal_muscle_index'}), (tgt:BodyLocation {name: 'muscular'}) MERGE (src)-[:MEASURED_AT {pmid: '38140308'}]->(tgt);
MATCH (src:BodyCompositionFeature {name: 'psoas_area'}), (tgt:BodyLocation {name: 'abdominal'}) MERGE (src)-[:MEASURED_AT {pmid: '37261678'}]->(tgt);
MATCH (src:BodyCompositionFeature {name: 'skeletal_muscle_index'}), (tgt:BodyLocation {name: 'brain'}) MERGE (src)-[:MEASURED_AT {pmid: '36909727'}]->(tgt);
MATCH (src:RadiomicFeature {name: 'first_order_mean'}), (tgt:BodyLocation {name: 'colon'}) MERGE (src)-[:MEASURED_AT {pmid: '34436440'}]->(tgt);
MATCH (src:RadiomicFeature {name: 'first_order_mean'}), (tgt:BodyLocation {name: 'heart'}) MERGE (src)-[:MEASURED_AT {pmid: '33494210'}]->(tgt);
MATCH (src:BodyCompositionFeature {name: 'subcutaneous_adipose_tissue'}), (tgt:ImagingModality {name: 'US'}) MERGE (src)-[:ACQUIRED_VIA {pmid: '29131365'}]->(tgt);
MATCH (src:ImagingModality {name: 'CT'}), (tgt:ImageRef {name: 'imageref:89b1e3b5e8a4e447'}) MERGE (src)-[:REPRESENTED_BY {}]->(tgt);
MATCH (src:Microbe {name: 'proteobacteria'}), (tgt:Disease {name: 'cirrhosis'}) MERGE (src)-[:POSITIVELY_CORRELATED_WITH {pmid: '39539377', confidence: 0.7}]->(tgt);
MATCH (src:Microbe {name: 'lactobacillus - based probiotics'}), (tgt:Disease {name: 'inflammatory bowel disease'}) MERGE (src)-[:NEGATIVELY_CORRELATED_WITH {pmid: '37998334', confidence: 0.7}]->(tgt);
MATCH (src:Microbe {name: 'bacteroidetes'}), (tgt:Disease {name: 'inflammatory bowel disease'}) MERGE (src)-[:NEGATIVELY_CORRELATED_WITH {pmid: '37998334', confidence: 0.7}]->(tgt);
MATCH (src:Microbe {name: 'peptostreptococcus stomatis'}), (tgt:Disease {name: 'cirrhosis'}) MERGE (src)-[:POSITIVELY_CORRELATED_WITH {pmid: '36536957', confidence: 0.7}]->(tgt);
MATCH (src:Microbe {name: 'ruminococcus'}), (tgt:Disease {name: 'cirrhosis'}) MERGE (src)-[:POSITIVELY_CORRELATED_WITH {pmid: '36536957', confidence: 0.7}]->(tgt);
MATCH (src:Microbe {name: 'bifidobacterium bifidum'}), (tgt:Disease {name: 'obesity'}) MERGE (src)-[:NEGATIVELY_CORRELATED_WITH {pmid: '36358288', confidence: 0.7}]->(tgt);
MATCH (src:Microbe {name: 'bifidobacterium lactis'}), (tgt:Disease {name: 'obesity'}) MERGE (src)-[:NEGATIVELY_CORRELATED_WITH {pmid: '36358288', confidence: 0.7}]->(tgt);
MATCH (src:Microbe {name: 'proteobacteria'}), (tgt:Disease {name: 'cirrhosis'}) MERGE (src)-[:POSITIVELY_CORRELATED_WITH {pmid: '35978666', confidence: 0.7}]->(tgt);
MATCH (src:Microbe {name: 'catenibacterium'}), (tgt:Disease {name: 'cirrhosis'}) MERGE (src)-[:NEGATIVELY_CORRELATED_WITH {pmid: '35978666', confidence: 0.7}]->(tgt);
MATCH (src:Microbe {name: 'actinobacteria species'}), (tgt:Disease {name: 'obesity'}) MERGE (src)-[:NEGATIVELY_CORRELATED_WITH {pmid: '35126309', confidence: 0.7}]->(tgt);
MATCH (src:Microbe {name: 'dysosmobacter'}), (tgt:Disease {name: 'obesity'}) MERGE (src)-[:NEGATIVELY_CORRELATED_WITH {pmid: '34108237', confidence: 0.7}]->(tgt);
MATCH (src:Microbe {name: 'lactobacillus - containing probiotic'}), (tgt:Disease {name: 'systemic inflammation'}) MERGE (src)-[:NEGATIVELY_CORRELATED_WITH {pmid: '33633246', confidence: 0.7}]->(tgt);

// --- Verify import ---
MATCH (n) RETURN labels(n)[0] AS label, count(n) AS count ORDER BY count DESC;
MATCH ()-[r]->() RETURN type(r) AS rel_type, count(r) AS count ORDER BY count DESC;